# ADR-002 — Agent-to-agent call contract (not subgraph composition)

**Status:** Accepted  
**Date:** 2026-09-25  
**Learning path:** B9d · [Preface](../README.md)  
**← Previous:** [ADR-001 Directory + unified invoke](adr-001-agent-directory-and-unified-invoke.md) · **Next:** [Environments](../platform/environments.md) →

## Chapter summary

**Primary A2A behavior** is Agent1 sending a request to Agent2, Agent2 performing
short or long work, and returning a response — including **multi-turn** on a
shared `conversation_id`. That is a **call contract** (directory → direct dial),
not an in-process LangGraph subgraph embed and not an A2A gateway proxy.

ADR-001 still owns directory bindings and HTTP dial mechanics. This ADR owns
**when** to use which mechanism and the **envelope** statuses.

---

## 1. Context

- Product intent: scenario-driven Agent1↔Agent2 interaction (request → work →
  response → optional further turns).
- In-process `invoke_agent` subgraphs merge compile-time graphs. They refuse
  session-enabled children and do not model long-running tasks or true
  multi-turn conversations between two agents.
- An A2A **gateway** (tool multiplex / protocol proxy) sits on every hop. That
  is optional policy later, not the composition spine.
- Engineers should structure **one** product agent with LangGraph subgraphs
  inside that agent. They should **not** split one workflow into many agents
  only so they can “compose” them in-process.

---

## 2. Decision

### 2.1 Preferred Agent1→Agent2 API

```text
call_agent(agent_id, input, conversation_id=…)
  → resolve (directory / local pack)
  → local MetadataAgent.invoke  OR  HTTP POST /agents/{id}/invoke
  → CallEnvelope
```

YAML `type: invoke_agent` **subgraph embed** remains available for optional
reuse of a **plain** registered pack in the same process. It is **not** the
recommended path for agentic A2A behavior.

### 2.2 Call envelope

| Field | Meaning |
|-------|---------|
| `agent_id` | Logical peer id |
| `request_id` | Per-hop correlation (tracing) |
| `conversation_id` | Multi-turn key (stable across turns) |
| `status` | See below |
| `state` | Flat result / message bag |
| `task_id` | Present when `status=running` |
| `session_id` | Present when HITL paused (compat) |

**Statuses**

| Status | Meaning | Caller action |
|--------|---------|----------------|
| `completed` | Work finished | Use `state` |
| `input_needed` | Peer needs another turn (clarify / HITL) | Same `conversation_id`, new input |
| `running` | Async accept (stub OK) | Poll `GET /agents/tasks/{task_id}` |
| `waiting` | HITL alias → treat as `input_needed` | Continue / resume session |

### 2.3 What we will not do

- Require an A2A gateway for Agent1↔Agent2.
- Replace local LangGraph structure with remote calls.
- Put URLs in `*.agent.yaml`.
- Make every product flow a multi-agent mesh.

### 2.4 Relation to ADR-001

| ADR-001 | ADR-002 |
|---------|---------|
| Directory + dialer + generic invoke | Envelope + multi-turn + `call_agent` |
| `invoke_agent` YAML (local/remote) | Demotes subgraph as optional reuse |
| Phases 0–4 + hardening | Call-contract semantics |

---

## 3. Flows

### 3.1 Multi-turn (happy path)

```text
Agent1                         Directory                    Agent2
  |  GET binding                 |                            |
  |----------------------------->|                            |
  |  POST /invoke {input, conversation_id=C}                  |
  |---------------------------------------------------------->|
  |  {status:completed, conversation_id:C, state…}            |
  |<----------------------------------------------------------|
  |  POST /invoke {input2, conversation_id=C}                 |
  |---------------------------------------------------------->|
  |  {status:completed, turn_count:2, …}                      |
  |<----------------------------------------------------------|
```

### 3.2 Async accept (worker)

```text
POST /invoke {…, async_accept:true}
  → {status:running, task_id:T, conversation_id:C}
  → in-process worker runs create_agent(…).invoke
GET  /agents/tasks/T
  → {status:running, …}           # while executing
  → {status:completed, state:…}   # or input_needed / error
```

Task persistence: ``EDIM_A2A_TASK_STORE=memory|file`` (file dir =
``EDIM_A2A_TASK_DIR``). Queue-scaled ACA / Service Bus workers remain a later
enterprise step; the poll contract stays the same.

---

## 4. Consequences

**Positive**

- Matches the product mental model (request/response + multi-turn).
- Keeps the framework simple: directory + dial + envelope; no gateway required.
- One agent + LangGraph subgraphs stays the default for single-team flows.

**Negative / follow-ons**

- Queue-scaled ACA / Service Bus workers are not in this ADR (in-process thread
  pool + memory/file task store is the local durable path).
- Official Google A2A protocol remains optional interoperability later.
- Existing `compose_parent`/`invoke_agent` demos stay as pack-reuse examples.

---

## 5. Related

| Doc / code | Role |
|------------|------|
| [ADR-001](adr-001-agent-directory-and-unified-invoke.md) | Directory + dial |
| [Orchestration topology](../framework/orchestration-topology.md) | Subgraph vs call |
| `edim_dde_ai.a2a.call.call_agent` | Preferred caller API |
| `edim_dde_ai.a2a.envelope` | Envelope helpers |
| Demo `a2a_partner` | Multi-turn peer |

## Summary

- **A2A = call contract**, not subgraph composition and not a gateway.
- Use **`conversation_id`** for multi-turn; **`task_id`** when `running`.
- Prefer **`call_agent`**; keep YAML subgraph embed as optional reuse only.

**Next →** [Environments (C1)](../platform/environments.md)

<!-- edim-learning-nav -->
---

← [ADR-001](adr-001-agent-directory-and-unified-invoke.md) · [Preface](../README.md) · [Environments](../platform/environments.md) →
