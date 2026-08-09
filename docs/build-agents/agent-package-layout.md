# Agent package layout

**Learning path:** F1 · [Guide home](../README.md)
**← Previous:** [Bundled agents](../domain/bundled-agents.md) · **Next:** [New agent step-by-step](step-by-step.md) →


Convention for every product or plugin agent:

```text
agents/<agent_id>/
  <agent_id>.agent.yaml   # required — graph + SQL + content_dir
  nodes.py                # required — @register_node adapters only
  logic.py                # recommended — state → partial updates
  helpers/                # optional — rules/data (not LangGraph-aware)
  content/                # optional — prompts/ + skills/ for llm_chain
  __init__.py
```

## Responsibilities

| Path | Owns |
|------|------|
| `*.agent.yaml` | Topology, `domain.sql.query` SQL, edges, routes/conditionals |
| `nodes.py` | Register type ids; call into `logic` |
| `logic.py` | Graph steps; orchestrate helpers |
| `helpers/` | Pure policy/data (sizing, guardrails, evidence assembly, …) |
| `content/` | Prompt/skill files referenced by `llm_chain` |

## Naming

- Folder name ≈ `agent_id`
- Type ids: `domain.<area>.*` for bundled agents; use a **vendor prefix** for plugins (`acme.tuning.*`)
- Shared SQL stays `domain.sql.query` (not under one agent)

## Anti-patterns

- Putting agent rules in top-level `edim_dde_domain/tools/` (that’s shared IO like `sql.py`)
- Fat `nodes.py` with business logic
- Secrets in YAML

<!-- edim-learning-nav -->
---

← [Bundled agents](../domain/bundled-agents.md) · [Guide home](../README.md) · [New agent step-by-step](step-by-step.md) →
