# Orchestration topology (D6)

**Learning path:** D6 · [Preface](../README.md)  
**← Previous:** [Content and LLM](content-and-llm.md) · **Next:** [HITL resume](hitl-resume.md) →

## Chapter summary

Multi-agent **structure** inside one product agent uses LangGraph subgraphs.
**Agent1↔Agent2** behavior uses a **call contract** (directory → dial →
envelope) — see [ADR-002](../architecture/adr-002-a2a-call-contract.md).
YAML `invoke_agent` subgraph embed is optional pack reuse, not the A2A path.

**Outcome:** one agent per product capability; call peers with `call_agent` /
generic invoke when you need request/response or multi-turn.

---

How multi-agent composition works without breaking the “one compile unit per agent id” packaging rule.

---

## 1. Rule

**One YAML agent definition per agent id.** Authors declare composition with
**`invoke_agent`** + logical `agent_id`. At resolve time:

| Outcome | When |
|---------|------|
| **Local subgraph** | Pack loaded and policy allows (`resolve=auto\|local`) |
| **Remote dial** | Directory/overlay says remote → HTTP dialer (`resolve=auto\|remote`) |

```text
parent.agent.yaml
  nodes:
    - prepare
    - call_child: type: invoke_agent → compose_leaf  (subgraph or HTTP)
    - summarize
```

---

## 2. Design patterns

| Pattern | Role |
|---------|------|
| **Composite** (structural) | Parent graph treats child agent as a node |
| **LangGraph subgraph** | Shared state → `add_node(compiled_child)`; mapped I/O → wrapper + `child.invoke` |
| **Remote dial** | Same YAML; `edim_dde_ai.a2a` dialer posts to peer `/agents/{id}/invoke` |
| **Facade** | Product still invokes `create_agent(parent_id)` |
| **Guard** | Compile-time `max_depth`, refuse self-call / cycles; session children refused (local) |

```text
Parent MetadataAgent (compile)
  → resolve(agent_id)           # auto | local | remote
  → local: build_graph(child) → native or mapped subgraph
  → remote: dialer node (HTTP …)
```

---

## 3. `invoke_agent` node

| Config key | Required | Meaning |
|------------|----------|---------|
| `agent_id` | yes | Target logical agent (never a URL) |
| `input_keys` | no | List of state keys to pass (default: **shared state** / native subgraph) |
| `output_map` | no | Map `child_key` → `parent_key` (implies mapped wrapper) |
| `max_depth` | no | Max nested **local** embed depth (default `3`) |
| `resolve` | no | `auto` (default via `EDIM_AGENT_RESOLVE`) \| `local` \| `remote` |

- **No `input_keys` / `output_map`:** child is attached with LangGraph
  `add_node(compiled_subgraph)` (shared flat `AgentState`).
- **With map:** LangGraph “call subgraph inside a node” with key transforms;
  child invoke receives LangGraph `config` with shared `request_id` and per-hop
  `span_id` / `parent_span_id`.
- Cycle / self-call / depth are checked **at compile time** (local path).
- Session-enabled agents cannot be **local** embed targets (use a plain child).

Child YAML stays a separate file — the parent only **references** `agent_id`.

### HITL interaction

- Prefer HITL gates on the **parent** (or a dedicated session agent).
- Do **not** embed session-enabled / checkpointer children as subgraphs.
- Mapped embeds wrap `skip_until_resume`; native shared-state subgraphs re-enter
  on resume (see [HITL resume](hitl-resume.md)).
- Cross-app HITL remains out of scope (resume against the runtime that owns the session).

---

## 4. Examples

| Location | Role |
|----------|------|
| `edim-dde-ai/examples/agents/invoke_agent_*.agent.yaml` | Framework mapped / native demos |
| Domain `compose_parent` → `compose_leaf` | Bootstrapped product/demo parent (Phase 1) |

---

## 5. Related ADR surfaces

| Surface | Role |
|---------|------|
| `GET/POST /api/v1/directory/*` | Bindings + register heartbeat |
| `POST /api/v1/agents/{id}/invoke` | Generic flat-state receiver (remote dial target) |
| `EDIM_AGENT_RESOLVE` | Process default `auto\|local\|remote` |
| `EDIM_AGENT_DIRECTORY_JSON` / `EDIM_DIRECTORY_URL` | Binding overlay / remote directory |

Still out of scope: cross-agent long-term memory; marketplace capability router;
full separate control-plane product (Phase 5 extract).

---

## 6. Related

| Doc | Topic |
|-----|--------|
| [ADR-001](../architecture/adr-001-agent-directory-and-unified-invoke.md) | Unified invoke + directory phasing |
| [Agent deployment & composition](../architecture/agent-deployment-and-composition.md) | Deploy shapes; §1b matrix |
| [Agent control plane](../architecture/agent-control-plane.md) | Legacy deep design (reference) |
| [HITL resume](hitl-resume.md) | `hitl.gate` + StateStore sessions |
| [YAML schema — session](yaml-schema.md#session) | Multi-turn + `EDIM_CHECKPOINTER` |
| [External plugins](../build-agents/external-plugins.md) | Loading packs into one runtime |

## Summary

- One YAML `invoke_agent`; framework resolves local subgraph vs network dial.
- Correlation (`request_id` / `span_id`) flows on mapped local and HTTP hops.

**Next →** [HITL resume](hitl-resume.md)

<!-- edim-learning-nav -->
---

← [Content and LLM](content-and-llm.md) · [Preface](../README.md) · [HITL resume](hitl-resume.md) →
