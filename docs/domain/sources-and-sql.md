# Sources and SQL

**Learning path:** E1 · [Preface](../README.md)  
**← Previous:** [Orchestration](../framework/orchestration-topology.md) · **Next:** [SQL design deep dive](../DESIGN_SOURCES_AND_SQL_NODES.md) →

## Chapter summary

Named Databricks SQL sources and the generic `domain.sql.query` collect pattern used by bundled agents. Covers skip/override keys that bypass live SQL for dry runs.

**Outcome:** you can read agent YAML SQL nodes and know when collectors no-op.

---

## Named sources

`config/sources.yaml` (shipped with domain) defines connection **shape** without secrets:

```yaml
sources:
  edim_sql_wh:
    type: databricks_sql
    server_hostname: ${DATABRICKS_HOST}
    http_path: ${DATABRICKS_HTTP_PATH}
```

## Within-env workspaces

When one `EDIM_ENV` has multiple Databricks workspaces, use the
[workspace / dataset resolver](workspace-resolver.md) (`config/workspaces.yaml`
+ request `workspace_id`). Hard rule: never cross env boundaries.

## `domain.sql.query`

Generic node: interpolate validated `${ENV}` table FQNs, bind `:name` params from state, execute, write `output_key`.

At invoke time it also applies the within-env workspace overlay (host/path +
table FQNs), then optional `bindings.sql-warehouse`.

Useful config keys:

- `source`, `query`, `params_from_state`, `params`
- `result_mode`: `rows` | `first_row`
- `on_empty`: `error` | `empty` (first_row)
- `skip_if_key`: see overrides below

## Overrides (skip warehouse, not LLM)

Before connecting, `domain.sql.query` short-circuits in either case:

1. **`output_key` already set** — e.g. tuning request passes `metrics`; collect node has `output_key: metrics`, so SQL is skipped.
2. **`skip_if_key` present and non-empty** — e.g. RCA SQL nodes set `skip_if_key: evidence_pack`. If the request already includes an assembled `evidence_pack`, every collect node no-ops. Downstream `assemble_evidence` keeps that override; classify + **`llm_chain` still run**.

`evidence_pack` itself is the structured RCA input (excerpts, anchors, refs) that the synthesize prompt consumes — normally built from SQL sections; injectable for tests/demos without Databricks.

Deep dive: [DESIGN_SOURCES_AND_SQL_NODES.md](../DESIGN_SOURCES_AND_SQL_NODES.md)

## Summary

- Sources define shape without secrets; one generic SQL node type collects data.
- Overrides (`metrics`, `evidence_pack`) skip SQL while LLM nodes still run.

**Next →** [SQL design deep dive (E2)](../DESIGN_SOURCES_AND_SQL_NODES.md)

<!-- edim-learning-nav -->
---

← [Orchestration](../framework/orchestration-topology.md) · [Preface](../README.md) · [SQL design deep dive](../DESIGN_SOURCES_AND_SQL_NODES.md) →
