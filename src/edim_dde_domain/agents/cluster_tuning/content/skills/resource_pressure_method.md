# Resource-pressure decision method

Use measured dimensions, not a fixed list of named scenarios:

1. Read every configured dimension in `sizing_hints.resource_pressure`.
2. Separate **pressure** (how heavily a resource is used), **headroom** (capacity
   still available), and **failure evidence** (explicit event/error data).
3. Use capacity pressure/headroom for worker-count direction.
4. Use the highest supported limiting-resource pressure for VM shape decisions.
   A shape change requires both high-enough pressure and a mismatch between the
   current shape and the configured preferred families.
5. If measured pressures are low, reduce capacity or tier conservatively while
   retaining the current resource shape. If pressures are moderate and healthy,
   avoid churn. If a dimension is high/saturated, preserve enough capacity and
   address that dimension.
6. Treat missing dimensions as unknown. Never manufacture disk, network, spill,
   throttling, skew, OOM, or job-failure evidence from CPU/memory percentages.

CPU, memory, and worker capacity are examples supplied by the current agent YAML.
The same procedure applies when another dimension is added.
