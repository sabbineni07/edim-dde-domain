# Sources and SQL

## Named sources

`config/sources.yaml` (shipped with domain) defines connection **shape** without secrets:

```yaml
sources:
  edim_sql_wh:
    type: databricks_sql
    server_hostname: ${DATABRICKS_HOST}
    http_path: ${DATABRICKS_HTTP_PATH}
```

## `domain.sql.query`

Generic node: interpolate validated `${ENV}` table FQNs, bind `:name` params from state, execute, write `output_key`.

Useful config keys:

- `source`, `query`, `params_from_state`, `params`
- `result_mode`: `rows` | `first_row`
- `on_empty`: `error` | `empty` (first_row)
- `skip_if_key`: skip SQL when another key already holds data (e.g. `evidence_pack`)

Deep dive: [DESIGN_SOURCES_AND_SQL_NODES.md](../DESIGN_SOURCES_AND_SQL_NODES.md)
