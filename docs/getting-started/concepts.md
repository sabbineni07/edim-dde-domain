# Core concepts (A2)

**Learning path:** A2 · [Preface](../README.md)  
**← Previous:** [Quickstart](quickstart.md) · **Next:** [Part B — Architecture](../architecture/index.md) →

## Chapter summary

This chapter defines the **vocabulary and mental models** used throughout the guide: agents, nodes, state, content, bootstrap, planes, and request overrides. Read it once before Part B.

**Outcome:** you can read `*.agent.yaml` and follow architecture discussions without ambiguity.

---

## 1. Agent

An **agent** is a named LangGraph compiled from `*.agent.yaml`, identified by `agent_id` (e.g. `cluster_tuning`, `spark_rca`).

```python
from edim_dde_ai import create_agent

final_state = create_agent("cluster_tuning").invoke({"job_id": "j-1", ...})
```

| Pattern | Role |
|---------|------|
| **Registry** | Lookup definition by `agent_id` |
| **Factory Method** | `create_agent(id)` returns a runnable graph |

Agents are registered at API startup via domain bootstrap — not hard-coded in the HTTP layer.

---

## 2. Node

A **node** is one step in the graph. YAML declares a **type id**; Python registers a factory:

```yaml
- id: synthesize
  type: llm_chain
  chain: rca
  output_key: llm_raw
```

```python
@register_node("domain.rca.classify_failure")
def classify_failure_factory(_config: dict):
    def _node(state: dict) -> dict:
        return logic.classify_failure(state)
    return _node
```

| Category | Example type ids |
|----------|------------------|
| Framework builtins | `passthrough`, `llm_chain`, `invoke_agent`, `rag.retrieve`, `hitl.gate` |
| Shared domain | `domain.sql.query` |
| Product / plugin | `domain.tuning.*`, `domain.rca.*` |

**Pattern:** Strategy — YAML selects behavior by allowlisted `type`; YAML **must not** embed Python import paths.

---

## 3. State

Graph **state** is a flat `dict`. Nodes return **partial updates** merged into the running state. OpenAPI response models (`RcaResponse`, `TuningResponse`) are separate projections at the HTTP boundary.

```text
invoke({job_run_id, …})
  → node A → {evidence_pack: …}
  → node B → {classification_hint: …}
  → merged state
  → API maps result field → response DTO
```

**Pattern:** one flat `AgentState` dict end-to-end — nodes return partial updates;
hosts (FastAPI, Agent Server) see the same product keys. There is no nested
LangGraph `data` bag.

Multi-turn product agents add a YAML `memory` + `session` block. FastAPI compiles
them via `build_session_graph` ≈ `build_graph` + initialize/converse/regenerate +
`EDIM_CHECKPOINTER`. See [YAML schema — session](../framework/yaml-schema.md#session).

---

## 4. Content

**Content** artifacts feed `llm_chain` nodes — prompts and skills under `content/` (typically `content_dir: ./content` in agent YAML).

| Artifact | Convention |
|----------|------------|
| System / human prompts | `content/prompts/{chain}.system.md`, `{chain}.human.md` |
| Skills | `content/skills/{name}.md` |

Placeholders `{var}` substitute from state keys at runtime.

---

## 5. Bootstrap

**Bootstrap** loads platform configuration and registers agents when the API process starts:

```text
load sources.yaml
load corpora.yaml
import agents/*/nodes.py          # register @register_node factories
register *.agent.yaml graphs
load EDIM_AGENT_DIRS plugins
configure observability / stores / retrieval from env
sync_registered_agents_to_store()
set_llm_provider (lazy Foundry on API)
```

Implementation entry point: `edim_dde_domain.bootstrap_agents()` invoked from `edim-dde-api` lifespan.

---

## 6. Hybrid YAML + Python model

| Layer | Owns | Must not |
|-------|------|----------|
| **YAML** | Topology, edges, SQL text in node config, `rag` / `metadata` blocks | Execute code or import modules |
| **Python** | Node factories, pure logic (`logic.py`, `helpers/`) | Define graph topology duplicated in YAML |

This separation keeps graphs reviewable in Git while preserving type-safe extensibility in code.

---

## 7. Planes (preview)

| Plane | Responsibility | R1 examples |
|-------|----------------|-------------|
| **Source control** | Graphs, prompts, runbooks | Git / Azure DevOps |
| **Control plane** | Catalog, sessions, audit | StateStore |
| **Knowledge** | Similarity search | RetrievalProvider, FAISS, Azure AI Search |
| **Data plane** | Graph execution, SQL, LLM | LangGraph, Foundry, Unity Catalog |
| **Observability** | Traces, eval hooks | LangSmith, MLflow |

Full treatment: [End-to-end design (B1)](../architecture/end-to-end-design.md).

---

## 8. Request overrides (HTTP)

| Field | Agent | Effect |
|-------|-------|--------|
| `metrics` | `cluster_tuning` | Skip SQL metric collection; use supplied object |
| `evidence_pack` | `spark_rca` | Skip SQL evidence collectors |

!!! warning
    Overrides do **not** disable LLM nodes unless the test harness stubs the LLM provider. Production callers should treat overrides as development and smoke aids unless explicitly supported by your API contract.

---

## Summary

| Term | One-line definition |
|------|---------------------|
| Agent | Named YAML graph, invoked by id |
| Node | Allowlisted step type + factory |
| State | Flat dict merged per step |
| Bootstrap | Startup registration and plane wiring |
| Plane | Swappable cross-cutting backend |

**Next →** [Part B — Architecture](../architecture/index.md) · [End-to-end design (B1)](../architecture/end-to-end-design.md)

← [Quickstart (A1)](quickstart.md) · [Part B — Architecture](../architecture/index.md) →
