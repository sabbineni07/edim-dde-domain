---
description: Product agent YAML conventions in edim-dde-domain
applyTo: "**/*.agent.yaml"
---

# Product agent YAML

- Node `type` values must be registered (`domain.*` or framework builtins).
- Prefer knobs on nodes (history, web search, signal_groups, resource_pressure) over new Python branches for thresholds.
- Keep runbook RAG (`rag.retrieve` / corpus) separate from experience/history composition.
- Web search: default `enabled: false` until production gateway is approved.
- `skip_if_key: evidence_pack` (or equivalent) for collectors when client supplies overrides.
- Do not embed secrets or connection strings in YAML.
