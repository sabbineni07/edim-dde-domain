# YAML schema contract (BL-002)

Canonical config contract for EDIM agents. Machine-readable schema:

[`edim-dde-ai/schemas/agent.schema.json`](../../../edim-dde-ai/schemas/agent.schema.json)

Validation runs during `parse_agent_definition` (structural) and optional JSON Schema checks for extended blocks.

---

## Required today

| Field | Type | Notes |
|-------|------|-------|
| `agent_id` | string | Stable id |
| `graph.nodes` | list | Non-empty; each has `id` + `type` |
| Graph entry | | `graph.entry` **or** a single `[START, node]` edge |

Also supported: `display_name`, `version` (int), `edges`, `conditional_edges` / `routes`, `content_dir`, inline `prompts` / `skills`.

---

## Extended blocks (R1 contract — optional keys)

These keys are reserved so agents can grow without renaming later. Phase 0 validates shape when present.

```yaml
agent_id: example
version: 1
metadata:
  owner: platform-team
  risk_tier: low          # low | medium | high
  lifecycle: draft        # draft | review | approved | deprecated
  hitl_required: false

model:
  ref: foundry-gpt-4o     # logical id; resolves via env/registry later

tools: []                 # future tool registry refs

rag: null                 # future RAG block

security:
  pii_redaction: true
  output_policy: null

evaluation:
  dataset: null           # LangSmith dataset name later

hitl:
  enabled: false

graph:
  nodes: [...]
  edges: [...]
```

---

## Breaking-change policy

1. Additive optional keys → minor schema version bump in docs
2. Removing/renaming required keys → major; provide migration notes
3. Existing R1 agents (`cluster_tuning`, `spark_rca`) remain valid without extended blocks

---

## CLI / library

```python
from edim_dde_ai.schema.validate import validate_agent_dict
validate_agent_dict(yaml_safe_load(path))  # raises DefinitionError on failure
```

Structural parse remains the source of truth for graph connectivity; JSON Schema covers metadata/extended blocks.
