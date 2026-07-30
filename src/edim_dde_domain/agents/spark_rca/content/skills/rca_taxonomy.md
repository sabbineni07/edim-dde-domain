# Spark failure taxonomy

## Spark failure taxonomy

| Category | Typical signals |
|----------|-----------------|
| sql_error | spark_sql_query_error, AnalysisException, table/column not found, parse/resolve failures |
| data_quality | null/constraint/schema mismatch, type mismatch, DELTA_SCHEMA-style messages |
| resource | OOM, disk full, executor lost, exit 137, many failed tasks, heavy spill |
| skew_shuffle | extreme shuffle read/write or duration imbalance across tasks/stages |
| timeout_or_cancel | cancelled, timeout, killed-by-user language |
| config | permission denied, missing secret, Connect/config errors |
| unknown | insufficient or conflicting evidence |