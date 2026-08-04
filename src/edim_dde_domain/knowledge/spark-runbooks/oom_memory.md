# Executor / driver OutOfMemoryError

## Signals
- `java.lang.OutOfMemoryError: Java heap space`
- Exit code 137 / SIGKILL under memory pressure
- High GC time vs executor runtime

## Likely causes
- Executor or driver heap too small for shuffle / broadcast / caching
- Missing `spark.executor.memoryOverhead` (~10–20% of executor memory)
- Large collect / broadcast of a big dataset to the driver

## Actions
1. Increase `spark.executor.memory` and/or `spark.driver.memory` when metrics show heap pressure.
2. Set `spark.executor.memoryOverhead` to ~15–20% of executor memory when spill/OOM co-occur.
3. Avoid `collect()` / large broadcasts; prefer distributed joins.
4. Check for skewed partitions amplifying per-task memory.
