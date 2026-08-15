# Resource pressure and capacity direction

Evaluate all resource dimensions configured by the agent. For each dimension,
separate the measured value, pressure level, source metrics, and whether evidence
is missing.

Decision method:
1. Use worker-capacity pressure and headroom to choose worker-bound direction.
   High headroom supports a conservative reduction; exhausted headroom supports
   preserving or increasing capacity.
2. Use per-resource pressure to identify the limiting resource. A VM shape change
   requires high-enough limiting pressure and a mismatch with the current shape.
3. When all measured pressures are low, reduce worker bounds first and then
   consider a smaller tier. Keep the current resource shape.
4. When measured pressure is moderate and demand has headroom, avoid churn.
5. When one dimension is high or saturated, preserve adequate aggregate capacity
   and address that dimension. Do not change worker count and VM shape together
   unless evidence supports both changes.
6. Treat unknown dimensions as unknown; do not fill gaps from workload names or
   historical cases.

Feature vocabulary is generated from configuration, for example
`cpu_pressure_low`, `memory_pressure_high`, `capacity_headroom_high`, and
`limiting_resource_memory`. These are examples, not a closed taxonomy.

Keywords: resource pressure, limiting resource, capacity headroom, worker demand,
autoscale ceiling, vCPU tier, resource shape, Databricks job cluster.
