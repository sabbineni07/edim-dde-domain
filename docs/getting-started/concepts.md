# Core concepts

## Agent

A named graph identified by `agent_id` (e.g. `cluster_tuning`, `spark_rca`). Declared in `*.agent.yaml`, registered into `edim-dde-ai`, invoked as:

```python
from edim_dde_ai import create_agent
final_state = create_agent("cluster_tuning").invoke({...})
```

## Node

A step in the graph. YAML references a **type id** string; Python registers a factory with `@register_node("type.id")`.

- **Builtin** (framework): `passthrough`, `set_value`, `echo_result`, `llm_chain`
- **Shared domain**: `domain.sql.query`
- **Product / plugin**: `domain.tuning.*`, `domain.rca.*`, `acme.*`, …

## State

Flat `dict` in / out. Nodes return **partial updates** merged into state. No typed schema on the graph itself (API response models are separate).

## Content

Prompts and skills for `llm_chain`, usually under `content/` next to the agent YAML (`content_dir: ./content`).

## Bootstrap

`edim_dde_domain.bootstrap_agents()`:

1. Load `sources.yaml`
2. Import each bundled `agents/*/nodes.py`
3. Register all nested `*.agent.yaml`
4. Optionally load [external plugins](../build-agents/external-plugins.md)

Hosts must also `set_llm_provider(...)` for LLM nodes (API does this in lifespan).

## Hybrid model

| Layer | Owns |
|-------|------|
| YAML | Topology, SQL text, node config, edges |
| Python | Node factories + pure helpers (`logic.py`, `helpers/`) |

YAML never embeds arbitrary Python import paths — only allowlisted type ids.
