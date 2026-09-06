# Orchestration topology (D6)

**Learning path:** D6 · [Preface](../README.md)  
**← Previous:** [Content and LLM](content-and-llm.md) · **Next:** [HITL resume](hitl-resume.md) →

## Chapter summary

Multi-agent composition under the rule **one YAML agent → one compile unit**,
using allowlisted `invoke_agent` which **embeds the child as a LangGraph
subgraph** at parent compile time. Deployment topology choices live in Part B.

**Outcome:** you compose agents in-process without ad-hoc Python orchestration in YAML.

---

How multi-agent composition works without breaking the “one compile unit per agent id” packaging rule.

---

## 1. Rule

**One YAML agent definition per agent id.** At compile time, parent graphs
**embed** children as LangGraph subgraphs (not a runtime phone-call to
`create_agent`). Authors still declare composition with allowlisted
**`invoke_agent`**.

```text
parent.agent.yaml
  nodes:
    - prepare
    - call_rca:   type: invoke_agent   → spark_rca  (compiled subgraph)
    - summarize
```

---

## 2. Design patterns

| Pattern | Role |
|---------|------|
| **Composite** (structural) | Parent graph treats child agent as a node |
| **LangGraph subgraph** | Shared state → `add_node(compiled_child)`; mapped I/O → wrapper + `child.invoke` |
| **Facade** | Product still invokes `create_agent(parent_id)` |
| **Guard** | Compile-time `max_depth`, refuse self-call / cycles; session children refused |

```text
Parent MetadataAgent (compile)
  → invoke_agent node
       → build_graph(child)           # plain flat child, recursive embeds
       → add_node(id, compiled)       # native when no input_keys/output_map
         or mapped wrapper            # when I/O map set
```

---

## 3. `invoke_agent` node

| Config key | Required | Meaning |
|------------|----------|---------|
| `agent_id` | yes | Target registered agent |
| `input_keys` | no | List of state keys to pass (default: **shared state** / native subgraph) |
| `output_map` | no | Map `child_key` → `parent_key` (implies mapped wrapper) |
| `max_depth` | no | Max nested embed depth (default `3`) |

- **No `input_keys` / `output_map`:** child is attached with LangGraph
  `add_node(compiled_subgraph)` (shared flat `AgentState`).
- **With map:** LangGraph “call subgraph inside a node” with key transforms.
- Cycle / self-call / depth are checked **at compile time**.
- Session-enabled agents cannot be embed targets (use a plain child agent).

Child YAML stays a separate file — the parent only **references** `agent_id`.

---

## 4. Example

See `edim-dde-ai/examples/agents/invoke_agent_parent.agent.yaml` (mapped),
`invoke_agent_native_parent.agent.yaml` (shared-state), and
`invoke_agent_child.agent.yaml`.

---

## 5. Not in current scope

- Cross-app remote invoke and agent control plane — **parked / design review:** [Agent control plane](../architecture/agent-control-plane.md) · [Agent deployment & composition](../architecture/agent-deployment-and-composition.md)  
- Cross-agent long-term memory  
- Capability-based router across a marketplace of agents (later)  
- HITL interrupt nodes — **shipped:** [HITL resume](hitl-resume.md)  
- HITL `skip_until_resume` around *native* shared-state subgraph nodes (mapped embeds still wrap skip)

---

## 6. Related

| Doc | Topic |
|-----|--------|
| [Agent deployment & composition](../architecture/agent-deployment-and-composition.md) | Option A/B/C topologies; DE SDLC; cross-app |
| [Agent control plane](../architecture/agent-control-plane.md) | **Design review** — governance, location registry, routing (Option B/C parked) |
| [HITL resume](hitl-resume.md) | `hitl.gate` + StateStore sessions (not LangGraph checkpointer) |
| [YAML schema — session](yaml-schema.md#session) | Multi-turn initialize/converse/regenerate + `EDIM_CHECKPOINTER` |
| [External plugins](../build-agents/external-plugins.md) | Loading packs into one runtime |

## Summary

- Use `invoke_agent` for composition; runtime is LangGraph subgraphs, not a separate phone-call orchestrator.
- Cross-app routing and control plane are design/parked elsewhere.

**Next →** [HITL resume](hitl-resume.md)

<!-- edim-learning-nav -->
---

← [Content and LLM](content-and-llm.md) · [Preface](../README.md) · [HITL resume](hitl-resume.md) →
