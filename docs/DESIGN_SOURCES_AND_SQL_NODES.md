# Design: Sources + Generic SQL Collect Nodes (E2)

**Learning path:** E2 · [Guide home](README.md)  
**← Previous:** [Sources and SQL](domain/sources-and-sql.md) · **Next:** [Bundled agents](domain/bundled-agents.md) →

**Status:** Implemented (Phases A–D)  
**Scope:** `edim-dde-domain` (+ thin use from `edim-dde-api`)  
**Out of scope:** Changes to `edim-dde-ai` core (graph engine stays generic)

---

## 1. Goal

Make data collection **declarative and reusable**:

- Named **sources** describe *how* to connect (Databricks SQL warehouse, etc.).
- Agent **nodes** declare *what* SQL to run (full query text + bind params).
- One **generic SQL node type** executes any use-case query.
- Use-case-specific **assembly** (e.g. evidence pack) stays small Python, not hardcoded collectors.

This replaces hard-coded `SparkSqlCollector` / `ClusterMetricsSqlCollector` query classes with YAML-driven collection.

---

## 2. Package responsibilities (unchanged)

| Package | Role |
|---------|------|
| `edim-dde-ai` | YAML graph → LangGraph; node/router registries; no Databricks knowledge |
| `edim-dde-domain` | Sources, SQL executor, generic `sql.query` node, agent YAMLs, assemble/analyze logic |
| `edim-dde-api` | HTTP; bootstrap domain; `create_agent().invoke(state)` |

---

## 3. High-level flow

```text
HTTP / invoke(state)
        │
        ▼
edim-dde-ai graph (*.agent.yaml)
        │
        ├─ sql.query node(s)          ← generic collect
        │     source + query + binds
        │     → rows / first_row in state
        │
        ├─ assemble_* (optional)      ← use-case shape (RCA pack, etc.)
        │
        └─ analyze nodes              ← classify / size / validate / explain
```

---

## 4. Sources

### 4.1 File layout

```text
edim-dde-domain/
  config/
    sources.yaml              # named connections (no secrets inline)
  src/edim_dde_domain/
    sources/
      loader.py               # load + validate sources.yaml
      resolve.py              # ${ENV} interpolation + token from env
      registry.py             # get_source(name) → ResolvedSource
    nodes/
      sql_query.py            # @register_node("domain.sql.query")
    tools/
      sql.py                  # shared named-param SQL IO
    agents/
      cluster_tuning/
        helpers/              # sizing, guardrails, SKU, optimization
      spark_rca/
        helpers/
          evidence_pack.py    # pure assemble (no IO)
```

### 4.2 `sources.yaml` shape

```yaml
sources:
  edim_sql_wh:
    type: databricks_sql
    server_hostname: ${DATABRICKS_HOST}          # or concrete hostname
    http_path: ${DATABRICKS_HTTP_PATH}           # or bare warehouse id / SQL_WAREHOUSE_ID
    # Auth is not in YAML. Runtime only:
    #   1) Databricks Apps — user OAuth via API middleware (set_request_databricks_token)
    #   2) Local dev — az login (DefaultAzureCredential)
```

### 4.3 Rules

- **Secrets** only via runtime credentials (never committed literals; no env PAT).
- `${VAR}` interpolation for host/path (and optionally other non-secret fields).
- `type` selects connector (`databricks_sql` first; later `postgres`, `local_stub`, …).
- Unknown source name → fail at bootstrap or first use with a clear error.
- Multi-workspace **within one `EDIM_ENV`**: [workspace resolver](domain/workspace-resolver.md)
  maps `workspace_id` → warehouse host/path + UC FQNs; cross-env entries are
  never registered (fail closed). Complements `bindings.sql-warehouse`.
- On Databricks Apps, API middleware calls `extract_forwarded_databricks_token` + `set_request_databricks_token` so SQL runs as the user.
### 4.4 Resolved source (runtime)

```text
ResolvedSource(
  name, type,
  server_hostname, http_path, access_token,
)
```

---

## 5. Generic node: `domain.sql.query`

### 5.1 Config (on the graph node)

```yaml
- id: collect_metrics
  type: domain.sql.query
  source: edim_sql_wh
  query: |
    SELECT
      CAST(job_id AS STRING) AS job_id,
      CAST(cluster_id AS STRING) AS cluster_id,
      azure_worker_vm_size,
      max_worker_nodes_provisioned,
      peak_worker_cpu_utilization_pct,
      peak_worker_memory_utilization_pct
    FROM catalog.schema.job_cluster_metrics
    WHERE CAST(job_id AS STRING) = :job_id
      AND CAST(cluster_id AS STRING) = :cluster_id
    ORDER BY job_run_date DESC
    LIMIT 1
  params_from_state: [job_id, cluster_id]
  # optional:
  # params:                    # static extras merged with state
  #   limit: 50
  result_mode: first_row       # rows | first_row (default: rows)
  output_key: metrics
  on_empty: error              # error | empty (default: empty for rows, error for first_row optional)
```

### 5.2 Behavior

1. Load `source` from registry → connection params.  
2. Build bind map from `params_from_state` (+ optional static `params`).  
3. Execute query with **bound parameters only** (no string format of state into SQL).  
4. Write result to `state[output_key]`.  
5. If `result_mode: first_row` and no rows → raise domain error (e.g. `NoJobMetricsError`) when `on_empty: error`.

### 5.3 Safety (non-negotiable)

| Allowed | Forbidden |
|---------|-----------|
| Full table FQN written by engineers in YAML | Table/FQN taken from request `state` and spliced into SQL |
| `:job_id` / `?` binds from state | `'{job_id}'` / f-string / `.format(state)` |
| Reviewed SQL in agent YAML | User-supplied SQL text from API body |

Engineers **may** hardcode `FROM catalog.schema.table_name` in the query text.

### 5.4 Override (tests / callers)

1. If `state[output_key]` already set → skip SQL (e.g. inject `metrics` in tests).  
2. Else if `skip_if_key` is set and present → skip (e.g. RCA `evidence_pack`).  
3. Else resolve source + execute; misconfigured source → `DatabricksNotConfiguredError`.

There is **no** production SQL stub flag (`EDIM_DOMAIN_ALLOW_STUB` removed).

---

## 6. Agent graphs (examples)

### 6.1 Cluster tuning

```yaml
agent_id: cluster_tuning
graph:
  entry: collect_metrics
  nodes:
    - id: collect_metrics
      type: domain.sql.query
      source: edim_sql_wh
      query: |
        SELECT ... FROM catalog.schema.job_cluster_metrics
        WHERE CAST(job_id AS STRING) = :job_id
          AND CAST(cluster_id AS STRING) = :cluster_id
        ORDER BY job_run_date DESC
        LIMIT 1
      params_from_state: [job_id, cluster_id, job_run_id]
      result_mode: first_row
      output_key: metrics
      on_empty: error

    - id: run_sizing
      type: domain.tuning.run_sizing
    - id: assess_risks
      type: domain.tuning.assess_risks
    - id: generate_recommendation
      type: domain.tuning.generate_recommendation
    - id: generate_explanation
      type: domain.tuning.generate_explanation

  edges:
    - [collect_metrics, run_sizing]
    - [run_sizing, assess_risks]
    - [assess_risks, generate_recommendation]
    - [generate_explanation, END]
  routes:
    - after: generate_recommendation
      when: { field: include_explanation, op: truthy }
      then: generate_explanation
      else: END
```

No `ClusterMetricsSqlCollector`.

### 6.2 Spark RCA (multi-query + assemble)

```yaml
agent_id: spark_rca
graph:
  entry: collect_failure_anchors
  nodes:
    - id: collect_failure_anchors
      type: domain.sql.query
      source: edim_sql_wh
      query: |
        SELECT ... FROM catalog.schema.spark_metrics
        WHERE CAST(job_run_id AS STRING) = :job_run_id
          AND event_type = 'pipeline_end'
          AND (...)
      params_from_state: [job_run_id, job_run_date, task_key]
      output_key: failure_anchors

    - id: collect_sql_plans
      type: domain.sql.query
      source: edim_sql_wh
      query: |
        SELECT ... FROM catalog.schema.spark_metrics
        WHERE ... event_type IN ('spark_sql_query_error', 'spark_sql_query_observed')
      params_from_state: [job_run_id, job_run_date, task_key]
      output_key: sql_plans

    - id: collect_error_logs
      type: domain.sql.query
      source: edim_sql_wh
      query: |
        SELECT ... FROM catalog.schema.spark_logs WHERE ...
      params_from_state: [job_run_id, job_run_date, task_key]
      output_key: error_logs

    - id: collect_timeline
      type: domain.sql.query
      source: edim_sql_wh
      query: |
        SELECT ... FROM catalog.schema.spark_metrics WHERE ...
      params_from_state: [job_run_id, job_run_date, task_key]
      output_key: timeline_events

    - id: collect_stage_pressure
      type: domain.sql.query
      source: edim_sql_wh
      query: |
        SELECT ... FROM catalog.schema.spark_metrics WHERE ...
      params_from_state: [job_run_id, job_run_date, task_key]
      output_key: stage_pressure

    - id: assemble_evidence
      type: domain.rca.assemble_evidence   # calls evidence_pack.build_evidence_pack
      # reads failure_anchors, sql_plans, error_logs, timeline_events, stage_pressure
      # writes evidence_pack

    - id: rule_classify
      type: domain.rca.classify_failure
    - id: synthesize
      type: domain.rca.synthesize
    - id: validate_output
      type: domain.rca.validate_output

  edges:
    - [collect_failure_anchors, collect_sql_plans]
    - [collect_sql_plans, collect_error_logs]
    - [collect_error_logs, collect_timeline]
    - [collect_timeline, collect_stage_pressure]
    - [collect_stage_pressure, assemble_evidence]
    - [assemble_evidence, rule_classify]
    - [rule_classify, synthesize]
    - [synthesize, validate_output]
    - [validate_output, END]
```

No `SparkSqlCollector`.  
Optional later: parallel collect fan-out if the framework adds it; v1 can stay sequential.

---

## 7. What we remove / keep

| Remove (or stop using) | Keep |
|------------------------|------|
| `SparkSqlCollector` (hardcoded queries) | `tools/sql.py` executor |
| `ClusterMetricsSqlCollector` | `agents/spark_rca/helpers/evidence_pack.py` assemble |
| `SparkTelemetryCollector` / `spark_telemetry.py` stub | YAML `domain.sql.query` nodes in `spark_rca.agent.yaml` |
| Env-only table settings as *required* for SQL text | `DomainSettings` for host/path fallback |
| Per-use-case collect logic that only wraps SQL | Analyze nodes (classify, sizing, validate) |

---

## 8. API impact

Minimal:

- Request body still passes ids (`job_run_id`, `job_id`, …) into state.  
- Optional overrides (`evidence_pack`, `metrics`) still short-circuit collect.  
- Errors: empty required query → 404; source not configured (stub off) → 503.  
- No SQL in the HTTP API.

---

## 9. Config vs secrets (summary)

```text
sources.yaml     → connection shape + ${ENV} refs
*.agent.yaml     → graph + full SQL (FQNs OK) + params_from_state
environment      → DATABRICKS_HOST / HTTP_PATH
                  tokens: Apps user OAuth (middleware) or local `az login`

```

---

## 10. Implementation phases

| Phase | Work |
|-------|------|
| **A** | `sources.yaml` + resolver; wire `execute_sql` to `ResolvedSource` |
| **B** | Register `domain.sql.query`; migrate cluster_tuning to one SQL node; delete `ClusterMetricsSqlCollector` |
| **C** | Migrate spark_rca to N SQL nodes + `assemble_evidence`; delete `SparkSqlCollector` |
| **D** | Docs + tests (override, bind params, empty→error); no production SQL stubs |

---

## 11. Open decisions (review)

1. **Param style:** `:name` (preferred) vs `?` + ordered `params_from_state` — Databricks SQL connector support to confirm in Phase A.  
2. **RCA collect:** sequential nodes (simple) vs single node with `queries: []` list (fewer graph nodes, less generic). **Recommend sequential generic nodes** for clarity.  
3. **Where SQL lives:** inline in `*.agent.yaml` (v1) vs `queries/*.sql` files referenced by path (v1.1 if YAML gets large).  
4. **Workspace overlays:** defer; single `sources.yaml` + per-env agent YAML FQNs for now.

---

## 12. Success criteria

- [ ] Any new agent can collect data with `domain.sql.query` + source + SQL in YAML only.  
- [ ] No use-case-specific SQL collector classes remain.  
- [ ] State values never concatenated into SQL strings.  
- [ ] Offline tests still work via override and/or stub.  
- [ ] API and `edim-dde-ai` remain unchanged in responsibility.

---

## 13. Non-goals (this design)

- MCP server exposure of the same tools (later, Option B).  
- Moving SQL into `edim-dde-ai` builtins.  
- User-authored SQL from the UI/API.

---

← [Sources and SQL](domain/sources-and-sql.md) · [Guide home](README.md) · [Bundled agents](domain/bundled-agents.md) →
