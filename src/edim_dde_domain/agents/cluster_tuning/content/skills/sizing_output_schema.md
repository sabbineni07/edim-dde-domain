## Sizing LLM JSON output (required keys)

- `pattern_analysis` — markdown with headings: Workload type, Resource utilization, Performance characteristics, Optimization opportunities
- `node_family` — one of D, E, F, L
- `vcpus` — integer 4–64
- `min_workers`, `max_workers` — integers; min ≤ max
- `auto_termination_minutes` — must be 0
- `rationale` — 2–4 sentences citing ingest metrics
