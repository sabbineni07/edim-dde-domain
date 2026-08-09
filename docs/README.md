# EDIM DDE — Engineer & developer guide

**Release:** R1 / `1.0.0` (Phase 0 foundation)  
**Audience:** platform engineers, agent authors, API operators  
**Browse:** local Docker serves this hub as **MkDocs Material** at `http://127.0.0.1:8080/guide/` (`make -C ../edim-dde-api guide-site && make -C ../edim-dde-api compose-up`). Sidebar + Previous / Next follow the learning path below. **Not** deployed to Databricks Apps.

> Temporary home: docs live under `edim-dde-domain/docs/` until a parent `edim` monorepo exists.

---

## Packages at a glance

| Package | Role |
|---------|------|
| [`edim-dde-ai`](../../edim-dde-ai/) | Framework: YAML → LangGraph, registries, builtins, observability, state store, retrieval |
| [`edim-dde-domain`](../) | Platform + product agents: sources, SQL, auth, Foundry, Key Vault, PII, RCA/tuning, corpora |
| [`edim-dde-api`](../../edim-dde-api/) | HTTP host: CORS, Apps token middleware, lifespan wiring, `/api/v1/*` |

Dependency direction: **`api` → `domain` → `ai`**.

---

## Learning path (read in this order)

### Part A — Start here

| Step | Page | What you learn |
|------|------|----------------|
| **A1** | [Quickstart](getting-started/quickstart.md) | Install, run API, call an endpoint |
| **A2** | [Core concepts](getting-started/concepts.md) | Agent, node, state, bootstrap, planes |

### Part B — Architecture & design (end-to-end)

| Step | Page | What you learn |
|------|------|----------------|
| **B1** | [**End-to-end design**](architecture/end-to-end-design.md) | Planes, request lifecycle, GoF patterns, diagrams |
| **B2** | [Architecture overview](architecture/overview.md) | Compact system sketch |
| **B3** | [Packages](architecture/packages.md) | Who owns what |
| **B4** | [Reference architecture (sign-off + PPT)](architecture/reference-architecture.md) | Review / deck / non-goals |
| **B5** | [HTML architecture deck](architecture/diagrams/r1-architecture-deck.html) | Slides for presentation |
| **B6** | [Request flow](architecture/request-flow.md) | One HTTP call, step by step |
| **B7** | [Auth and SQL](architecture/auth-and-sql.md) | Identity paths into the warehouse |
| **B8** | [Config → observability](architecture/config-to-observability.md) | YAML → registries → traces + store + retrieval |
| **B9** | [**Agent deployment & composition**](architecture/agent-deployment-and-composition.md) | One app vs many; DE SDLC; cross-app; **§1b capability matrix** |

### Part C — Platform planes (same order as API lifespan)

API startup configures concerns in roughly this order — docs follow it so mental model matches runtime.

**Security / access topic map (keep separate):**

| Need | Page |
|------|------|
| App roles / trust boundaries | **C2** Security baseline |
| Who is U / A / B on Local, Apps, ACA | **C2b** Access & permissions |
| Key Vault + `EDIM_KV_SECRET_MAP` | **C2c** Key Vault bootstrap |
| Package & grant ACA MI warehouse/UC | **G3** Deploy & hosting |

| Step | Page | Plane |
|------|------|-------|
| **C1** | [Environments](platform/environments.md) | SDBX / DEV / PROD matrix |
| **C2** | [Security baseline](platform/security-baseline.md) | Trust boundaries, app role matrix (docs) |
| **C2b** | [**Access & permissions**](platform/access-and-permissions.md) | Identities U/A/B — who runs SQL / Foundry / KV per host |
| **C2c** | [**Key Vault bootstrap**](platform/key-vault-bootstrap.md) | Vault auth order, `EDIM_KV_SECRET_MAP`, examples |
| **C3** | [PII guardrails](platform/pii-guardrails.md) | Redaction before logs/traces |
| **C4** | [Observability providers](platform/observability.md) | LangSmith / MLflow / none |
| **C5** | [LangSmith setup](platform/langsmith-setup.md) | Projects, keys, local vs SaaS |
| **C6** | [Control-plane state store](platform/state-store.md) | Postgres / Cosmos / Redis / memory |
| **C7** | [Retrieval & RAG](platform/retrieval-and-rag.md) | FAISS / Azure AI Search / Databricks; spark_rca pilot |

### Part D — Framework (`edim-dde-ai`)

| Step | Page | What you learn |
|------|------|----------------|
| **D1** | [YAML schema contract](framework/yaml-schema.md) | Canonical agent config |
| **D2** | [YAML agents](framework/yaml-agents.md) | Loading & registration |
| **D3** | [Nodes and routers](framework/nodes-and-routers.md) | Type ids, factories |
| **D4** | [Conditional edges](framework/conditional-edges.md) | Branching |
| **D5** | [Content and LLM](framework/content-and-llm.md) | Prompts, skills, Foundry |
| **D6** | [Orchestration (`invoke_agent`)](framework/orchestration-topology.md) | Nested agents |

Deep dive (package-owned): [edim-dde-ai DESIGN](../../edim-dde-ai/docs/DESIGN.md) · [USAGE](../../edim-dde-ai/docs/USAGE.md)

### Part E — Domain agents & SQL

| Step | Page | What you learn |
|------|------|----------------|
| **E1** | [Sources and SQL](domain/sources-and-sql.md) | Named sources + `domain.sql.query` |
| **E2** | [Sources & SQL design (deep)](DESIGN_SOURCES_AND_SQL_NODES.md) | Why one SQL node |
| **E3** | [Bundled agents](domain/bundled-agents.md) | `cluster_tuning`, `spark_rca` |

### Part F — Build your own agent

| Step | Page | What you learn |
|------|------|----------------|
| **F1** | [Agent package layout](build-agents/agent-package-layout.md) | Directory contract |
| **F2** | [New agent step-by-step](build-agents/step-by-step.md) | Authoring checklist |
| **F3** | [External plugins](build-agents/external-plugins.md) | `EDIM_AGENT_DIRS` / entry points |

### Part G — API host

| Step | Page | What you learn |
|------|------|----------------|
| **G1** | [Configuration](api/configuration.md) | Env for a working API |
| **G2** | [HTTP endpoints](api/endpoints.md) | OpenAPI surface |
| **G3** | [**Deploy & hosting**](api/deploy-and-hosting.md) | Apps create (console/CLI/CI), naming `edim-dde-api-*`, packaging A–D, KV grant |

### Part H — Reference & contribute

| Step | Page | What you learn |
|------|------|----------------|
| **H1** | [Environment variables](reference/env-vars.md) | Full env catalog |
| **H2** | [Node type ids](reference/node-type-ids.md) | Allowlisted types |
| **H3** | [Glossary](reference/glossary.md) | Terms |
| **H4** | [Testing](contribute/testing.md) | How we test |
| **H5** | [Live & dry smoke test](contribute/live-smoke-test.md) | Engineer runbook: env checklist, local + remote |
| **H5b** | [Windows smoke checklist](contribute/windows-smoke-checklist.md) | Same smoke, PowerShell / Windows steps |
| — | [Product backlog](../../BACKLOG.md) | Day-to-day EDIM |
| — | [Platform capability backlog](../../AI_Framework_Platform_Capability_Backlog.md) | Enterprise roadmap |

---

## Mental model (one diagram)

```text
┌──────────── SOURCE CONTROL (Git / Azure DevOps) ────────────┐
│  *.agent.yaml · prompts · skills · runbooks · corpora.yaml  │
└────────────────────────────┬────────────────────────────────┘
                             │ bootstrap / Jobs ingest
     ┌───────────────────────┼───────────────────────┐
     ▼                       ▼                       ▼
 CONTROL PLANE          KNOWLEDGE PLANE          DATA PLANE
 StateStore             RetrievalProvider        LangGraph + SQL + LLM
 (catalog/session)      (FAISS/Azure/DBX)        (do the work)
     │                       │                       │
     └───────────────────────┼───────────────────────┘
                             ▼
                    OBSERVABILITY PLANE
                    LangSmith / MLflow
```

Start at **[B1 — End-to-end design](architecture/end-to-end-design.md)** after A1–A2 if you need the full picture before coding.

---

## Navigation convention

Every major page includes a footer:

```text
← Previous · Guide home · Next →
```

Follow **Next** to stay on the learning path without jumping topics randomly.
