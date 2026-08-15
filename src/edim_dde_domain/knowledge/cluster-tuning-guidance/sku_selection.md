# Cluster worker SKU family selection

When changing Azure worker VM size:
- Stay on the allow-listed SKU set.
- Keep the current family when no configured dimension reaches the threshold for
  a shape change.
- Map the supported limiting resource to the preferred families configured by the
  agent. The current Azure mapping uses E for memory, F/D for CPU/general demand,
  and L only when an explicit storage dimension or storage evidence is available.
- Prefer the smallest vCPU tier that still meets peak fitness after
  `validate_performance` capacity checks.
- Guardrails clamp illegal min/max workers and auto-termination; treat clamps
  as hard policy, not suggestions.

Keywords: sku, node_family, vcpus, allow-list, guardrails, D-series, E-series,
F-series, L-series, Databricks cluster sizing.
