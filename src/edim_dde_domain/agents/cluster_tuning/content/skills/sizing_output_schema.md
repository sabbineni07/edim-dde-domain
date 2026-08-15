## Sizing LLM JSON output (required keys)

- `pattern_analysis` — markdown with headings: Workload type, Resource utilization,
  Performance characteristics, Optimization opportunities, Historical evidence
- `node_family` — one of D, E, F, L
- `vcpus` — integer 4–64
- `min_workers`, `max_workers` — integers; min ≤ max
- `auto_termination_minutes` — must be 0
- `rationale` — 2–4 sentences citing ingest metrics

`pattern_analysis` must say whether history corroborated or was rejected; never
claim a historical outcome when `historical_context` is `None`.
