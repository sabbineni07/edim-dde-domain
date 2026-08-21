# Agent package layout

**Learning path:** F1 · [Preface](../README.md)  
**← Previous:** [External add-ons](../domain/external-addons.md) · **Next:** [New agent step-by-step](step-by-step.md) →

## Chapter summary

Directory convention for every product or plugin agent: required YAML and `nodes.py`, recommended `logic.py`, optional `helpers/` and `content/`.

**Outcome:** you can scaffold a package that bootstrap and plugins will discover.

---

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

## Summary

- Keep adapters thin; put rules in helpers/logic, not fat `nodes.py`.
- No secrets in YAML; reuse `domain.sql.query` for Databricks IO.

**Next →** [New agent step-by-step (F2)](step-by-step.md)

<!-- edim-learning-nav -->
---

← [External add-ons](../domain/external-addons.md) · [Preface](../README.md) · [New agent step-by-step](step-by-step.md) →
