# Cluster worker SKU family selection

When changing Azure worker VM size:
- Stay on the allow-listed SKU set (E-series memory-optimized defaults for
  typical ETL; D-series when CPU-bound and memory headroom is ample).
- Prefer the smallest vCPU tier that still meets peak fitness after
  `validate_performance` capacity checks.
- Guardrails clamp illegal min/max workers and auto-termination; treat clamps
  as hard policy, not suggestions.

Keywords: sku, Standard_E8s_v3, node_family, vcpus, allow-list, guardrails,
Databricks cluster sizing.
