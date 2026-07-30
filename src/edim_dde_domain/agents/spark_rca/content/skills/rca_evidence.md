# Evidence pack usage

## Evidence pack usage

- Prefer pipeline_end.failure_reason and spark_sql_query_error attributes.
- When present, also use sql_text, physical_plan, logical_plan, join_types, and shuffle-related attributes from SQL events.
- Correlate logs via job_run_id, task_key, spark_app_id.
- Cite evidence[].ref values only — never fabricate refs.
- Keep timeline_highlights short (3–8 items around the failure).
- Truncated excerpts are normal; do not invent the missing text.