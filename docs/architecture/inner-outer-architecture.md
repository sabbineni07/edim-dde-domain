# Inner vs outer architecture (B1b)

**Learning path:** B1b · [Preface](../README.md)  
**← Previous:** [End-to-end design](end-to-end-design.md) · **Next:** [Architecture overview](overview.md) →

## Chapter summary

EDIM DDE uses two complementary views of the same system:

- **Inner** — how a **single agent** is built and run (orchestrator, tools, model, memory, host). This is what we ship in R1.
- **Outer** — how the **platform** will govern and connect many agents over time (location, policy, health, optional gateway). This is planned, not built yet.

This chapter defines that vocabulary, shows what we run today, and states what we plan to add — without changing the six planes in [End-to-end design](end-to-end-design.md).

**Outcome:** you can explain what is R1 versus target, and where inner work stops and outer platform work begins.

**Prerequisites:** [End-to-end design (B1)](end-to-end-design.md) · [Agent control plane (B9b)](agent-control-plane.md) (design only)

---

## 1. Two views (do not mix them)

| View | Question it answers | Status |
|------|---------------------|--------|
| **Inner** | What is *one* agent made of, and how does a request run through it? | **R1 — shipped** |
| **Outer** | How will we locate, authorize, and operate *many* agents as a platform? | **Target — planned** (Phases 4–5) |

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ OUTER (platform) — planned                                               │
│  Clients · optional Agent Gateway · many runtimes · registries · IAM     │
│  governance CP (location, policy, health) · AuthZ · evals · FinOps later │
│  Detail: agent-control-plane.md · tracked in BACKLOG Phase 4–5           │
└─────────────────────────────────────────────────────────────────────────┘
         │ hosts / invokes
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ INNER (one agent) — R1                                                   │
│  FastAPI transaction → LangGraph orchestrator (YAML)                     │
│  Tools (SQL/domain nodes) · Model client (llm_chain→Foundry) · RAG       │
│  Optional HITL/eval in-graph · Host IAM (U/A/B) · LangSmith telemetry    │
│  Shipped under Option A (one App, many agents in-process)                │
└─────────────────────────────────────────────────────────────────────────┘
```

!!! note "Hosting shapes are not planes"
    Option **A / B / C** (one App vs split Apps vs hub + location) are **deploy topologies**. They do not add boxes to the six-plane model. See [Agent deployment](agent-deployment-and-composition.md).

---

## 2. Inner architecture (what we run)

A request enters the API host, runs one YAML-defined LangGraph agent, calls tools and the model as needed, and returns a result. That whole path is the **inner** architecture.

### 2.1 Layout

```text
 Interaction                Core (edim-dde-ai + domain YAML)
 ┌──────────────┐          ┌─────────────────────────────────────────────┐
 │ User/curl    │  Input   │ Goal = request state                        │
 │ Apps /docs   │ ───────► │ Orchestrator = LangGraph from *.agent.yaml  │
 │ (future UI)  │ ◄─────── │   nodes · routers · invoke_agent            │
 └──────────────┘  Result  │ Eval strip: quality rubrics · hitl.gate     │
                           │ Tools: domain.sql.query · product nodes     │
                           │ Model: llm_chain + LLMProvider              │
                           │ Memory: flat state (short) · stores/RAG     │
                           │         (long — RecStore / corpora)         │
                           ├─────────────────────────────────────────────┤
                           │ Agent runtime (edim-dde-api host)           │
                           │  plugins: obs / store / retrieval           │
                           │  hosting: Apps / Docker / uvicorn           │
                           │  posture: allowlisted types · PII · strict  │
                           └───────┬───────────┬───────────┬─────────────┘
                                   │ tools     │ model     │ telemetry
                                   ▼           ▼           ▼
                           SQL / UC / RAG  Foundry LLM   LangSmith
                           domain nodes    (direct)      / MLflow
                           Host IAM: U (SQL Apps) · A (KV) · B (Foundry)
```

### 2.2 Flow legend

| Flow | Meaning | Path in EDIM |
|------|---------|--------------|
| **Transaction** | Request in, result out | HTTP → FastAPI → `create_agent().invoke` → DTO |
| **Tool use** | Agent reads or acts on platform data | Domain nodes / SQL / RAG retrieve → state |
| **Model invocation** | LLM call | `llm_chain` → Foundry (`EDIM_FOUNDRY_*`) |
| **Telemetry** | Traces and eval side channel | ObservabilityProvider → LangSmith / MLflow |
| **IAM** | Who may call SQL, Key Vault, Foundry | Middleware token (U), App SP (A), Foundry SP (B) |

### 2.3 Package map

| Inner piece | Package / artifact |
|-------------|--------------------|
| Interaction + hosting | `edim-dde-api` |
| Orchestrator, model client, registries, HITL gate, plane APIs | `edim-dde-ai` |
| Tools, Foundry adapter, PII, bundled workflows | `edim-dde-domain` |
| Workflow definition | Git `*.agent.yaml` + `content/` |

---

## 3. Outer architecture (what we plan)

**Outer** is the platform layer around many agents: how callers find them, whether they may run, health and lifecycle, and (optionally) a northbound gateway. We do **not** implement this in R1. Design detail lives in [Agent control plane](agent-control-plane.md); sequencing is BACKLOG Phases 4–5.

```text
┌── Data plane (transactions) ──────────────────────────────────────────┐
│ Clients → [optional Agent Gateway] → Agent runtimes (Apps / ACA)       │
│            → optional model / tool gateways → Foundry / tools / KB     │
└────────────────────────────────────────────────────────────────────────┘
┌── Control plane (target — extends R1 narrow CP) ───────────────────────┐
│ Location · policy · health · lifecycle · optional gateway              │
│ Broader asset catalogs (agents / tools / models) · AuthZ · FinOps later│
│ Observability, evals, and guardrails as shared platform services       │
└────────────────────────────────────────────────────────────────────────┘
```

| Capability | R1 today | Target (Phase 4–5) |
|------------|----------|---------------------|
| Client / UI | API is the front door | Future UI |
| Northbound gateway | FastAPI only | Optional Agent Gateway |
| Agent runtimes | One process, many agents | Option B split when domain boundaries need it |
| Agent-to-agent | `invoke_agent` in-process | Remote invoke + shared correlation ids |
| Model / tool gateways | Direct Foundry + allowlisted node types | Only if tool/model sprawl demands it |
| Catalogs | Registry + `AgentRecord` | Broader agents / tools / models catalog |
| Control plane | Narrow StateStore (catalog, sessions, audit) | Location, policy, health — [control plane design](agent-control-plane.md) |
| Identity | Host U/A/B + Key Vault | Stronger agent identity later |
| Authorization | Host + UC grants | Richer AuthZ later |
| FinOps | — | Phase 5 |
| Observability | LangSmith / MLflow | Same + cross-hop spans |
| Evaluations / guardrails | Quality harness + PII | Continuous / stronger |

!!! warning "Do not implement from this section"
    Outer work is gated on Apps live E2E (Phase 0) and inner hardening (Phase 2). Prefer **directory before gateway**.

---

## 4. Six planes stay; control plane has two scopes

Keep the six planes from [End-to-end design §2](end-to-end-design.md#2-planes-system-design). Do **not** add Memory, Tool, Gateway, or IAM as planes.

| Plane | R1 meaning |
|-------|------------|
| Source control | Git graphs / prompts |
| **Control (narrow)** | StateStore: agent **catalog**, HITL **sessions**, **audit** |
| **Control (target)** | Same plane **extended**: location, policy, health, optional gateway — not a seventh plane |
| Knowledge | RetrievalProvider |
| Data | LangGraph + SQL + Foundry (+ in-graph tools) |
| Observability | LangSmith / MLflow |
| Ingest | Jobs + curated ingest API |

### Three “catalog” words (do not confuse)

| Term | Meaning |
|------|---------|
| **Unity Catalog** | Databricks tables (data plane) |
| **Agent catalog** | `AgentRecord` in StateStore (control narrow) |
| **Asset catalog** (target outer) | Broader agents / tools / models product registry |

---

## 5. R1 vs target capability matrix

| Capability | R1 | Later |
|------------|----|-------|
| YAML → LangGraph agents | Yes | — |
| Option A (one App, many agents) | Yes | Remains default |
| HITL framework + `hitl_demo` | Yes | Product gates = Phase 2 decision |
| Narrow control (catalog / sessions / audit) | Yes | — |
| Knowledge / RAG providers | Yes | Default Azure AI Search = Phase 3 |
| Direct Foundry (no model gateway) | Yes | Gateway optional Phase 5 |
| Option B / C hosting | Parked | Phase 4 |
| Location registry / remote invoke | No | Phase 4 |
| Agent Gateway / tool gateway | No | Phase 4–5 |
| Rich AuthZ / FinOps / agent identity | No | Phase 5 |

---

## 6. How we expand (phased)

| Phase | Theme | Tracker (workspace `BACKLOG.md`) |
|-------|--------|----------------------------------|
| **0** | Close Apps live E2E (**IAM blocker**) | Phase 0 |
| **1** | This vocabulary and dual-view (docs) | Phase 1 |
| **2** | Inner hardening (product HITL, eval) | Phase 2 |
| **3** | Platform depth under Option A (stores, RAG, CI) | Phase 3 |
| **4–5** | Outer control plane / Option B–C | Phase 4–5 |

---

## Summary

- **Inner** is what we run: one agent’s orchestrator, tools, model, optional HITL/eval, and host.  
- **Outer** is what we plan: platform location, policy, health, and optional gateways around many agents.  
- **Six planes stay**; control is **narrow** today and **target** later on the same plane.  
- Expansion follows BACKLOG phases 0→5; Phase 0 remains the IAM blocker for Apps live E2E.

**Next →** [Architecture overview (B2)](overview.md) · or [Agent control plane (B9b)](agent-control-plane.md) for target control-plane detail

← [End-to-end design](end-to-end-design.md) · [Architecture overview](overview.md) →
