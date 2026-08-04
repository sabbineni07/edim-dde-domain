# Small files and tiny tasks

## Signals
- Very high task count with tiny input bytes per task
- Long job time dominated by scheduling overhead
- Many small Delta/Parquet files in listing

## Actions
1. Compact with OPTIMIZE / bin-packing writes.
2. Increase target file size; avoid excessive partitioning.
3. Use `repartition` / `coalesce` thoughtfully before write.
4. Review auto-optimize / optimized writes settings on Delta tables.
