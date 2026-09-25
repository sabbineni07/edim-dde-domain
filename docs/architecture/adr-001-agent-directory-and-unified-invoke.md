# ADR-001 — Unified `invoke_agent` + Agent Directory (co-located → extract)

**Status:** Accepted (implementation phased)  
**Date:** 2026-09-06  
**Learning path:** B9c · [Preface](../README.md)  
**← Previous:** [Agent control plane (legacy design)](agent-control-plane.md) · **Next:** [Environments](../platform/environments.md) →

## Chapter summary

One YAML composition surface (`invoke_agent` + logical `agent_id`). The runtime
resolves **local subgraph** vs **network** dial. An **Agent Directory** starts
as read APIs on `edim-dde-api` (Phase 2) and may later move to a separate
governance service. This ADR **supersedes Option A/B/C as the primary taxonomy**
and reframes the parked control-plane doc as background, not the build spine.

**Update (2026-09-25):** Prefer the [ADR-002 call contract](adr-002-a2a-call-contract.md)
(`call_agent` + multi-turn envelope) for Agent1↔Agent2. In-process YAML
`invoke_agent` subgraphs remain for optional pack reuse, not the A2A path.

---

## 1. Context

### 1.1 What we have today

- In-process composition: YAML `type: invoke_agent` embeds another registered
  agent as a **LangGraph subgraph** at compile time
  ([Orchestration topology](../framework/orchestration-topology.md)).
- Hosting default: one FastAPI process (`edim-dde-api`) with product routes;
  ACA Native standard, Databricks Apps compatibility.
- **No** remote A2A, **no** generic `/agents/{id}/invoke`, **no** location registry.
- Older docs describe Option B (split apps + remote) / Option C (hub + catalog)
  and a large [agent control plane](agent-control-plane.md) design — **parked**,
  partly outdated vs subgraphs + ACA-first hosting.

### 1.2 Decision drivers

- Authors must not learn three YAML dialects for local vs remote vs “ask directory.”
- URLs must not appear in agent graphs.
- Directory / governance must **not** execute graphs, SQL, or Foundry.
- Start small on the existing API; extract when multiple runtimes need a shared
  system of record.

---

## 2. Decision

### 2.1 One YAML command

Authors always write:

```yaml
- id: call_child
  type: invoke_agent
  agent_id: spark_rca          # logical only — never a URL
  input_keys: [job_run_id]     # optional
  output_map: { root_cause: rca }  # optional
  max_depth: 3                 # optional
  # resolve: auto              # optional later: auto | local | remote
```

The **framework** chooses:

| Outcome | When |
|---------|------|
| **Local subgraph** | Pack loaded in this process and policy allows |
| **Remote dial** | Directory (or static binding) says remote → HTTP / later MCP / … |

### 2.2 Three runtime modes (not three YAML modes)

```text
1. Same process     → subgraph embed (implemented)
2. Direct remote    → caller already has binding / dials HTTP|MCP
3. Resolved remote  → ask directory for binding, then dial like (2)
```

### 2.3 Agent Directory

- **v1 (Phase 2):** read APIs under `edim-dde-api`  
  `/api/v1/directory/...` — bindings derived from in-process registry + optional
  env overlay (`EDIM_AGENT_DIRECTORY_JSON`).
- **Later:** same contract hosted as a **separate** service (teams, policy, cost,
  guardrails, heartbeat). Runtimes set `EDIM_DIRECTORY_URL`.

Directory returns **metadata + how to call**. It does **not** proxy invoke traffic
(directory-first / Model D). Optional northbound **gateway** remains a separate
product decision.

### 2.4 What we will not build

- Separate YAML node types per mode (`remote_invoke_agent` as authoring default).
- URLs inside `*.agent.yaml` graphs.
- Control plane that runs LangGraph / SQL / Foundry.
- Full governance before remote dial works end-to-end.

### 2.5 Relation to Option A/B/C

| Old label | New framing |
|-----------|-------------|
| Option A | Default **pack placement**: many agents, one runtime |
| Option B | **Pack placement** choice: few domain runtimes (ops); composition still one YAML |
| Option C | Superseded by **Directory** (+ optional later CP extract) |

Keep [agent-deployment-and-composition.md](agent-deployment-and-composition.md)
for deploy shapes; use **this ADR** for composition + directory sequencing.

---

## 3. Target flows

### 3.1 Auto resolve (target after Phase 4)

```text
invoke_agent(agent_id)
  ├─ local pack loaded? → LangGraph subgraph
  └─ else Directory GET /directory/agents/{id}
        → transport/endpoint → dialer (HTTP …)
        → map I/O; depth + correlation headers
```

### 3.2 Directory (east-west)

```text
Runtime A ──GET /api/v1/directory/agents/{id}──► Directory
Runtime A ──POST invoke (direct to Runtime B)──► Runtime B
              (directory not on invoke data path)
```

---

## 4. Phased implementation plan

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **0** | This ADR; retire A/B/C as primary composition taxonomy | **Done** |
| **1** | Harden local subgraph path; correlation; product/demo parent composition | **Done** (`compose_parent` / `compose_leaf`; mapped invoke passes `request_id`/`span_id`) |
| **2** | Directory **read** APIs on `edim-dde-api` | **Done** |
| **3** | Generic `POST /api/v1/agents/{agent_id}/invoke` receiver | **Done** |
| **4** | Resolver + HTTP dialer behind `invoke_agent` (`EDIM_AGENT_RESOLVE`) | **Done** (`edim_dde_ai.a2a`) |
| **5** | Directory register/heartbeat + `EDIM_DIRECTORY_URL` client; optional separate service | **Partial** — in-process register + URL client; extract app still open |
| **6+** | Extra transports (MCP, managed agents) as dialer plugins | **Partial** — plugin registry + MCP stub; real MCP later |

Tracking: workspace [`BACKLOG.md`](../../../BACKLOG.md) § P2 multi-agent · platform **BL-027**.

---

## 5. Phase 2 API contract (stubs)

| Method | Path | Behavior (v1) |
|--------|------|----------------|
| `GET` | `/api/v1/directory/health` | Directory readiness |
| `GET` | `/api/v1/directory/agents` | List bindings for this env |
| `GET` | `/api/v1/directory/agents/{agent_id}` | Resolve one binding (`404` if unknown) |
| `POST` | `/api/v1/directory/register` | Upsert runtime binding (heartbeat MVP) |
| `POST` | `/api/v1/agents/{agent_id}/invoke` | Generic flat-state invoke (Phase 3) |

**Binding fields (stable):** `agent_id`, `env`, `mode` (`local`\|`remote`),
`transport` (`in_process`\|`http`\|…), `endpoint`, `invoke_path`, `version`,
`healthy`, `metadata`.

Local bindings: one entry per `list_agents()` id, `mode=local`,
`transport=in_process`. Optional JSON overlay may mark remotes (Phase 2 overlay;
dialer unused until Phase 4).

---

## 6. Consequences

**Positive**

- Single mental model for authors; deploy topology stays independent.
- Incremental delivery; extract CP without rewriting graphs.
- Aligns with ACA-first hosting and subgraph-based local compose.

**Negative / risks**

- Until Phase 4, directory is observational only (no auto remote).
- Co-located directory shares blast radius with the runtime (accepted for MVP).
- Generic invoke (Phase 3) expands attack surface — interim `EDIM_A2A_TOKEN` AuthZ shipped; full SSO remains BL-056.

---

## 7. Related

| Doc | Role |
|-----|------|
| [Orchestration topology](../framework/orchestration-topology.md) | Local `invoke_agent` / subgraphs today |
| [Agent deployment & composition](agent-deployment-and-composition.md) | Deploy shapes; §1b matrix |
| [Agent control plane](agent-control-plane.md) | Legacy deep design (gateway/heartbeat) — reference only |
| [Agent Runtime Hosting Architecture](../../../Agent_Runtime_Hosting_Architecture.md) | ACA / planes / portability |
| `edim-dde-ai/examples/agents/invoke_agent_*.agent.yaml` | Author templates |

## Summary

- **One YAML `invoke_agent`.** Framework resolves local vs network.
- **Directory** starts on `edim-dde-api`; later may become a separate app.
- **Do not** implement three configuration languages or YAML URLs.

**Next →** [Environments (C1)](../platform/environments.md)

<!-- edim-learning-nav -->
---

← [Agent control plane](agent-control-plane.md) · [Preface](../README.md) · [Environments](../platform/environments.md) →
