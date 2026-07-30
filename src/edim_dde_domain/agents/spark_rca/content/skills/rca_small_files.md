# Small files

## RULE: Small file / high metadata overhead

- **Signal:** Very large task counts with tiny per-task runtime (e.g. many tasks < ~100ms) and/or high FileScan file counts / tiny input bytes per task in plan or stage metrics when present.
- **Diagnostic:** Table layout has many uncompacted small files causing scheduling/metadata overhead.
- **Fix (when justified by evidence):**
  - Delta `OPTIMIZE table_name ZORDER BY (...)` or Liquid Clustering (`CLUSTER BY (...)`)
  - Enable auto-compaction, e.g. `SET spark.databricks.delta.autoOptimize.autoCompact = true;`
- Put OPTIMIZE/CLUSTER guidance in `recommendations.code_query_rewrites` or infra notes; put `SET` statements in `recommendations.spark_delta_configs`.
- Do not invent table names — only use names visible in the pack; otherwise say “OPTIMIZE the scanned Delta table identified in the plan/SQL.”
- Often pairs with category `config` or `sql_error`/`resource` depending on whether failure vs degradation dominates.