# Driver/Executor OOM

## RULE: Driver OOM / Executor OOM (resource)

### Driver out-of-memory (OOM)
- **Signal:** `java.lang.OutOfMemoryError: Java heap space` on the driver, or `CollectExec` (or similar collect-to-driver) operators in physical_plan / plan attributes when present.
- **Diagnostic:** Large result collected to driver via `.collect()`, `.toPandas()`, `show` on huge data, or an overly aggressive `spark.sql.autoBroadcastJoinThreshold`.
- **Fix:** Prefer direct writes / bounded display; reduce broadcast threshold; increase driver node memory only when evidence supports driver-side pressure.
- Map category toward `resource` when driver OOM is primary.

### Executor OOM / container killed (exit code 137)
- **Signal:** Container killed for exceeding memory limits (YARN/K8s), exit code 137, executor lost, and/or high `memoryBytesSpilled` + `diskBytesSpilled` in stage metrics.
- **Diagnostic:** Oversized partitions, heavy Python UDF memory use, or insufficient `spark.executor.memoryOverhead`.
- **Fix:** Increase `spark.sql.shuffle.partitions`; replace Python UDFs with native/vectorized functions when logs suggest UDF pressure; set `spark.executor.memoryOverhead` (~20% of executor memory) when spill/OOM co-occur.
- Prefer exact `SET` statements in `recommendations.spark_delta_configs` when justified by pack signals.

Tie every recommendation to cited evidence; if signals are partial, phrase as low-confidence investigatory checks.