# Part D — Framework

**Learning path:** D0 · [Preface](../README.md)  
**← Previous:** [Retrieval & RAG](../platform/retrieval-and-rag.md) · **Next:** [YAML schema](yaml-schema.md) →

## Chapter overview

Part D covers **`edim-dde-ai`**: how YAML agent definitions compile into LangGraph graphs, how node types and routers register, and how orchestration, HITL, and evaluation extend the runtime without forking the engine.

**After completing Part D you will:**

- Author valid `*.agent.yaml` against the schema contract.
- Register node factories and wire conditional edges.
- Compose nested agents and optional human-in-the-loop gates.

---

## Prerequisites

| Requirement | Chapter |
|-------------|---------|
| Core vocabulary | [Core concepts (A2)](../getting-started/concepts.md) |
| Graph compilation model | [End-to-end design §1 (B1)](../architecture/end-to-end-design.md) |

Package-local deep dives also exist in `edim-dde-ai/docs/DESIGN.md` and `USAGE.md` (not duplicated here).

---

## Chapters in this part

| Step | Chapter | Topic |
|------|---------|-------|
| **D1** | [YAML schema](yaml-schema.md) | Canonical contract |
| **D2** | [YAML agents](yaml-agents.md) | Load and register |
| **D3** | [Nodes and routers](nodes-and-routers.md) | Type ids, factories |
| **D4** | [Conditional edges](conditional-edges.md) | Branching |
| **D5** | [Content and LLM](content-and-llm.md) | Prompts, Foundry chains |
| **D6** | [Orchestration](orchestration-topology.md) | `invoke_agent` |
| **D6b** | [HITL resume](hitl-resume.md) | Gates, sessions, resume API |
| **D7** | [Evaluation & quality](evaluation-and-quality.md) | Rubrics, harness |

---

## Design rules for framework consumers

1. **Extend via registered node types**, not YAML `import` hacks.
2. **Keep agents free of HTTP** — expose through `edim-dde-api` when needed.
3. **Use `hitl.gate` explicitly** — bundled product graphs do not pause by default.
4. **Do not copy LangSmith `request_id` into agent state bags** — correlation stays in API/middleware.

!!! tip "Pro tip"
    Validate YAML early with schema tests in `edim-dde-ai` before wiring new node types — failures are cheaper at compile time than at first `invoke`.

---

## Summary

Part D is the reference for agent **structure**. Part E applies these patterns to SQL-backed product agents.

**Next →** [YAML schema (D1)](yaml-schema.md)
