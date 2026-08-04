# Shuffle skew and straggling tasks

## Signals
- One task duration >> peers (e.g. >5x median)
- Uneven shuffle read bytes across tasks
- Stage succeeds but wall-clock dominated by few tasks

## Likely causes
- Hot keys in joins / groupBys
- Unbalanced partitions after repartition

## Actions
1. Inspect key distribution; salt hot keys when justified.
2. Increase `spark.sql.shuffle.partitions` carefully for large shuffles.
3. Prefer AQE (`spark.sql.adaptive.enabled=true`) when available.
4. Consider broadcast join only when the build side is small.
