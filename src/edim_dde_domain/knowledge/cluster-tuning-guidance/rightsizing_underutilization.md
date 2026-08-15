# Cluster worker rightsizing — underutilization

When peak worker CPU and memory stay well below capacity while
`max_worker_nodes_provisioned` is high relative to
`avg_worker_nodes_consumed` / `p99_worker_nodes_consumed`, prefer
**downsizing max workers** before changing SKU family.

Guidance:
- Target ~90% of observed peak demand with ~10% headroom (sizing policy).
- Prefer reducing `max_workers` when p99 nodes << provisioned max.
- Keep driver SKU stable unless driver metrics show saturation.
- Do not invent cost dollars; use relative capacity / resource optimization %.

Keywords: underutilization, rightsizing, max_workers, peak_cpu, peak_memory,
worker nodes, Databricks job cluster.
