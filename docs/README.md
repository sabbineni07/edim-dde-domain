# EDIM DDE — Engineer & developer guide

**Release:** R1 / `1.0.0`  
**Audience:** platform engineers, agent authors, API operators  
**Browse:** local Docker serves this hub as **MkDocs Material** at `http://127.0.0.1:8080/guide/` (`make -C ../edim-dde-api guide-site && make -C ../edim-dde-api compose-up`). Sidebar + Previous / Next follow the learning path below. **Not** deployed to Databricks Apps.

> Temporary docs hub under `edim-dde-domain/docs/` (ownership / ADO Wiki / publish path still open — see `BACKLOG.md` revisit item). Markdown here is the source; MkDocs builds the `/guide` reader.

---

## Packages at a glance

| Package | Role |
|---------|------|
| `edim-dde-ai` | Framework: YAML → LangGraph, registries, builtins, observability, state store, retrieval |
| `edim-dde-domain` | Platform + product agents: sources, SQL, auth, Foundry, Key Vault, PII, RCA/tuning, corpora |
| `edim-dde-api` | HTTP host: CORS, Apps token middleware, lifespan wiring, `/api/v1/*` |

Dependency direction: **`api` → `domain` → `ai`**. (Sibling checkouts next to each other under your workspace.)

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
| **B5** | [Architecture deck](architecture/architecture-deck.md) | HTML slides + SVG assets for presentation |
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
| **C2b-flow** | [**Authentication flows**](platform/authentication-flows.md) | Visual auth: User → Apps → API → UC / RAG / Foundry / stores / LangSmith |
| **C2c** | [**Key Vault bootstrap**](platform/key-vault-bootstrap.md) | Vault auth order, `EDIM_KV_SECRET_MAP`, examples |
| **C3** | [PII guardrails](platform/pii-guardrails.md) | Redaction before logs/traces |
| **C4** | [Observability providers](platform/observability.md) | LangSmith / MLflow / none |
| **C5** | [LangSmith setup](platform/langsmith-setup.md) | Projects, keys, local vs SaaS |
| **C6** | [Control-plane state store](platform/state-store.md) | `EDIM_STATE_STORE` — agent catalog / sessions / audit (examples in guide) |
| **C6b** | [Recommendation lifecycle store](platform/recommendation-store.md) | `EDIM_RECOMMENDATION_STORE` — tuning/RCA history rows + status; [Cosmos §4b](platform/recommendation-store.md#4b-setting-up-cosmos-for-edim_recommendation_storecosmos) |
| **C7** | [Retrieval & RAG](platform/retrieval-and-rag.md) | FAISS / Azure AI Search / Databricks; [Azure setup §8](platform/retrieval-and-rag.md#8-setting-up-azure-ai-search-for-a-real-retrievalprovider) |

### Part D — Framework (`edim-dde-ai`)

| Step | Page | What you learn |
|------|------|----------------|
| **D1** | [YAML schema contract](framework/yaml-schema.md) | Canonical agent config |
| **D2** | [YAML agents](framework/yaml-agents.md) | Loading & registration |
| **D3** | [Nodes and routers](framework/nodes-and-routers.md) | Type ids, factories |
| **D4** | [Conditional edges](framework/conditional-edges.md) | Branching |
| **D5** | [Content and LLM](framework/content-and-llm.md) | Prompts, skills, Foundry |
| **D6** | [Orchestration (`invoke_agent`)](framework/orchestration-topology.md) | Nested agents |
| **D7** | [Evaluation & quality](framework/evaluation-and-quality.md) | Rubrics, corpus `v1`, Foundry harness |

Deep dive (in the `edim-dde-ai` package): `docs/DESIGN.md` · `docs/USAGE.md`

### Part E — Domain agents & SQL

| Step | Page | What you learn |
|------|------|----------------|
| **E1** | [Sources and SQL](domain/sources-and-sql.md) | Named sources + `domain.sql.query` |
| **E2** | [Sources & SQL design (deep)](DESIGN_SOURCES_AND_SQL_NODES.md) | Why one SQL node |
| **E3** | [Bundled agents](domain/bundled-agents.md) | Map of `cluster_tuning`, `spark_rca` |
| **E3a** | [**Agents deep dive**](domain/agents-guide.md) | Section hub — shared deps |
| **E3b** | [Cluster tuning walkthrough](domain/cluster-tuning-agent.md) | Input → every node → TuningResponse + diagrams |
| **E3c** | [Spark RCA walkthrough](domain/spark-rca-agent.md) | Multi-SQL → RAG → RcaResponse + diagrams |
| **E3d** | [UC telemetry tables](domain/uc-telemetry-tables.md) | Table FQNs + attribute meanings |
| **E3e** | [External add-ons](domain/external-addons.md) | Knowledge/RAG, ingest, Foundry, Knowledge Assistant |

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
| — | Workspace root `BACKLOG.md` | Day-to-day EDIM (Git; not in this site) |
| — | Workspace root `AI_Framework_Platform_Capability_Backlog.md` | Enterprise roadmap (Git; not in this site) |

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

**Primary (MkDocs Material):** sidebar sections A–H and footer **Previous / Next** follow `mkdocs.yml` `nav` (same order as the learning path above).

**In-page labels:** each major page also shows `Learning path: …` plus Previous/Next links at the top (and often a matching footer). Those should match the Material order — if they ever disagree, treat **`mkdocs.yml` as source of truth** and fix the page header.
