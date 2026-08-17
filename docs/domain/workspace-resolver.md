# Within-env workspace / dataset resolver

**Learning path:** E1b · [Guide home](../README.md)
**← Previous:** [Sources and SQL](sources-and-sql.md) · **Next:** [SQL design deep dive](../DESIGN_SOURCES_AND_SQL_NODES.md) →


## Hard rule

One process / App is bound to **one** `EDIM_ENV` (`sdbx` / `dev` / `prod` / …). Agents and resolvers **never** resolve warehouse hosts or Unity Catalog FQNs in another env (no `dev` → `prod` SQL).

Within that env there may be **multiple Databricks workspaces** (e.g. `dev_1`, `dev_2`, `dev_3`). The resolver picks among those only.

```text
EDIM_ENV=dev  ──►  workspaces.yaml entries with env: dev  ✓
                   workspaces.yaml entries with env: prod  ✗ (never registered)
```

---

## What it resolves

| Concern | Source |
|---------|--------|
| SQL warehouse host / HTTP path | Catalog entry or process `DATABRICKS_HOST` / `DATABRICKS_HTTP_PATH` |
| UC table FQNs for agent SQL `${…}` | Catalog `tables:` or process `DATABRICKS_*_TABLE` |
| Which workspace | Request `workspace_id` → else `EDIM_DEFAULT_WORKSPACE_ID` → else sole catalog entry / `default` |

Logical table keys in YAML map to the env names already used in agent SQL:

| Catalog key | Agent SQL `${VAR}` |
|-------------|-------------------|
| `job_cluster_metrics` | `DATABRICKS_JOB_CLUSTER_METRICS_TABLE` |
| `spark_metrics` | `DATABRICKS_SPARK_METRICS_TABLE` |
| `spark_logs` | `DATABRICKS_SPARK_LOGS_TABLE` |

---

## Config

`config/workspaces.yaml` (repo root preferred; package ships empty `workspaces: {}`):

```yaml
workspaces:
  dev_1:
    env: dev
    server_hostname: ${DATABRICKS_HOST_DEV_1}
    http_path: ${DATABRICKS_HTTP_PATH_DEV_1}
    tables:
      job_cluster_metrics: catalog_dev1.schema.job_cluster_metrics
      spark_metrics: catalog_dev1.schema.spark_metrics
      spark_logs: catalog_dev1.schema.spark_logs
  # prod_1: { env: prod, ... }  ← ignored when EDIM_ENV=dev
```

When the catalog is empty for the process env, the runtime falls back to a single synthetic workspace (`default`, or `EDIM_DEFAULT_WORKSPACE_ID`) built from process `DATABRICKS_*` — same behaviour as before this feature.

Optional env:

| Variable | Purpose |
|----------|---------|
| `EDIM_DEFAULT_WORKSPACE_ID` | Default when the request omits `workspace_id` (required if the catalog has **multiple** within-env entries) |

---

## Request flow

```text
POST /api/v1/...  body.workspace_id = "dev_1"
        │
        ▼
agent.invoke(state)  ── state.workspace_id
        │
        ▼
domain.sql.query
        │
        ├─ resolve_workspace_dataset(workspace_id)   # fail closed
        │     • skip / refuse other EDIM_ENV entries
        │     • overlay table FQNs into SQL ${ENV}
        │     • overlay host/path unless bindings win
        │
        ├─ bindings.sql-warehouse (optional)         # beats workspace host/path
        │
        └─ execute_sql(source, bound SQL)
```

**Precedence (host/path):** `bindings.sql-warehouse` → workspace catalog → `sources.yaml` / process `DATABRICKS_*`.

**API:** RCA already accepts `workspace_id`; cluster tuning `TuningRequest` does as well. Both pass through `model_dump()` into agent state.

---

## Fail closed

| Situation | Behaviour |
|-----------|-----------|
| Catalog entry `env` ≠ process `EDIM_ENV` | Not registered; id not selectable |
| Request `workspace_id` unknown for this env | `DomainToolError` |
| Dataset somehow tagged with another env | `DomainToolError` at resolve |
| Multi-workspace catalog without default / request id | `DomainToolError` at load |
| Bad UC FQN in catalog | `DomainToolError` at load |

---

## Relation to other seams

| Seam | Role |
|------|------|
| `sources.yaml` | Named connection shape + token auth |
| Workspace resolver | Within-env pick of warehouse + UC FQNs |
| `bindings.sql-warehouse` | Rare **per-agent** host/path overlay (compile-time) |

Complementary — not replacements.

---

## Tests

`tests/test_workspace_resolver.py` — catalog filter, cross-env refusal, process fallback, SQL node overlay, bindings precedence.

<!-- edim-learning-nav -->
---

← [Sources and SQL](sources-and-sql.md) · [Guide home](../README.md) · [SQL design deep dive](../DESIGN_SOURCES_AND_SQL_NODES.md) →
