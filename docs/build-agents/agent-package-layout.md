# Agent package layout

**Learning path:** F1 · [Preface](../README.md)  
**← Previous:** [External add-ons](../domain/external-addons.md) · **Next:** [New agent step-by-step](step-by-step.md) →

## Chapter summary

Directory convention for every product or plugin agent: required YAML and
`nodes.py`, recommended `logic.py`, optional `helpers/` and `content/`. The
same package is the graph artifact for ACA Native, Standalone Agent Server on
ACA, and Full self-hosted LangSmith Deployment on AKS.

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

## Deployment contract

The agent package must be host-neutral:

- YAML contains topology and non-secret configuration, not credentials.
- `nodes.py` registers allowlisted node types; it does not choose a host.
- `logic.py` contains product behavior and returns partial state updates.
- Graph construction must not call SQL, Foundry, Key Vault, or LangSmith.
- Runtime providers and identities arrive through environment configuration.

ACA Native uses the FastAPI host and `build_graph()`. The optional Agent Server
adapter uses `build_flat_graph()` and an explicit graph factory such as
`cluster_tuning_graph`. Full self-hosted LangSmith consumes the same packaged
factory through its Agent Server deployment process. See [Deployment targets
and release runbook](../api/deployment-targets.md).

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
