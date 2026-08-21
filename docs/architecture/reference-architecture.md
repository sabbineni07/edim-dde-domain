# EDIM DDE — Release 1 reference architecture

**Learning path:** B4 · [Preface](../README.md)  
**← Previous:** [Packages](packages.md) · **Next:** [Architecture deck](architecture-deck.md) →

## Chapter summary

Approved **R1 reference map** for the EDIM AI agent stack: packages, trust boundaries, request flow, environments, and explicit non-goals. Use this page for architecture review and PowerPoint export; operational how-tos live in Parts C–G.

**Outcome:** you can defend R1 scope boundaries and point reviewers at the signed-off diagrams.

---

**Status:** BL-001 — **signed off 2026-08-05**  
**Audience:** Architecture review and PowerPoint export  
**Version:** R1 (`1.0.0` package baseline)

This document is the **approved reference map** for the EDIM AI agent stack: packages, trust boundaries, request flow, environments, and R1 non-goals.

---

## Sign-off

| Role | Name | Date | Decision |
|------|------|------|----------|
| First sign-off | Stakeholder (product/architecture owner) | 2026-08-05 | **Approved** — R1 architecture |

---

## Presentation assets (PPT)

| Asset | Path | Use |
|-------|------|-----|
| **HTML slide deck (9 slides)** | [diagrams/r1-architecture-deck.html](diagrams/r1-architecture-deck.html) | Open in Chrome → **Present** → screenshot each 1280×720 slide into PPT |
| System context SVG | [diagrams/r1-system-context.svg](diagrams/r1-system-context.svg) | Insert into PPT as vector (preferred over PNG) |
| Request sequence SVG | [diagrams/r1-request-sequence.svg](diagrams/r1-request-sequence.svg) | Insert into PPT as vector |
| Environment deploy SVG | [diagrams/r1-environments.svg](diagrams/r1-environments.svg) | Insert into PPT as vector |

**How to build the PPT quickly**

1. Open the HTML deck in Chrome (allows Simple Icons CDN for brand marks).
2. Click **Present** (fullscreen) and capture slides 01–09.
3. For the three detailed diagrams, prefer **Insert → Picture → SVG** from the files above (crisper in Zoom/print).
4. Icons in the HTML deck use [Simple Icons](https://simpleicons.org/) (Databricks, LangChain, FastAPI). The Azure mark is an inlined Simple Icons SVG (`data:` URI) because `cdn.simpleicons.org/microsoftazure` currently 404s. For final Marketing brand packs, swap logos if required.

---

## 1. System context

```text
┌────────────────────┐     HTTPS      ┌──────────────────────────────────────┐
│  Clients           │───────────────►│  edim-dde-api (FastAPI)               │
│  • curl / Postman  │                │  • CORS · user token · request_id    │
│  • Databricks Apps │                │  • Key Vault bootstrap               │
│  • Future UI       │                │  • ObservabilityProvider             │
└────────────────────┘                │  • StateStore (control plane)        │
                                      └───────────────┬──────────────────────┘
                         ┌────────────────────────────┼────────────────────────────┐
                         │ invoke                     │                            │
                         ▼                            ▼                            ▼
               ┌───────────────────┐     ┌────────────────────┐     ┌────────────────────┐
               │ edim-dde-ai       │     │ StateStore         │     │ LangSmith / MLflow │
               │ YAML → LangGraph  │     │ postgres (local)   │     │ Observability      │
               │ invoke_agent      │     │ cosmos (deployed)  │     └────────────────────┘
               └─────────┬─────────┘     │ redis | memory     │
                         │               └────────────────────┘
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   Databricks UC   Azure Foundry   Azure DevOps Git
   (telemetry)     (LLM)           (*.agent.yaml SoT)
```

**Planes:** source control (Git) · control plane (StateStore) · data plane (SQL/LLM/graphs) · observability (LangSmith).

**Git vs store:** `*.agent.yaml` stays in Azure DevOps. StateStore holds catalog metadata synced at bootstrap — see [state-store.md](../platform/state-store.md).

Domain package (`edim-dde-domain`) still owns sources, SQL nodes, PII, and bundled agents (`cluster_tuning`, `spark_rca`) on the data plane; Azure Foundry serves LLM completions; Databricks UC is the warehouse.

**Trust boundaries**

| Boundary | What crosses it | Auth |
|----------|-----------------|------|
| Client → API | JSON over HTTPS | Apps gateway / network; CORS allow-list (Swagger `/docs` on App URL OK) |
| API → SQL | Queries via `domain.sql.query` | **U:** Apps `X-Forwarded-Access-Token` + User auth scope `sql`; local: `az login` |
| API → Foundry | Chat completions | **B:** `EDIM_FOUNDRY_*` (from Key Vault via **A** App SP); local: `az login` if unset |
| Runtime → LangSmith | Traces (redacted) | `LANGCHAIN_API_KEY` / project per env |
| Runtime → StateStore | Catalog / sessions / audit | Postgres URL, Cosmos keys, or Redis URL |

---

## 2. Package responsibilities

| Package | Version | Responsibility |
|---------|---------|----------------|
| **edim-dde-ai** | 1.0.0 | YAML schema, LangGraph builder, registries, `llm_chain`, `invoke_agent`, ObservabilityProvider, **StateStore** (memory/postgres/cosmos/redis) |
| **edim-dde-domain** | 1.0.0 | Named SQL sources, auth, Foundry adapter, Key Vault load, bundled agents, domain PII patterns |
| **edim-dde-api** | 1.0.0 | HTTP surface, CORS, Apps token + `RequestId` middleware, lifespan (KV + observability + state store + catalog sync), `/api/v1/*`, safe boundary logging |

Dependency direction: `api` → `domain` → `ai`.

---

## 3. R1 non-goals (explicit)

Deferred past Release 1:

- Full MCP connector mesh (ADO / ServiceNow / JIRA)
- Enterprise RAG / Azure AI Search platform (framework **RetrievalProvider spike** + `spark_rca` pilot exist; full knowledge platform / retention still later)- HITL review UI
- Governance dashboard / risk questionnaires
- Enforced RBAC roles beyond current identity paths (role **matrix is documented**; enforcement is later)

---

## 4. Logical request flow (detail)

See also [request-flow.md](request-flow.md) and the sequence SVG.

```text
Client
  │  POST /api/v1/cluster_tuning/recommend  (+ X-Request-Id optional)
  ▼
API middleware
  │  Bind Databricks user token (Apps)
  │  Bind request_id (X-Request-Id or UUID); echo on response; logs [request_id=…]
  ▼
Route handler
  │  Validate body (Pydantic)
  │  asyncio.to_thread(create_agent("cluster_tuning").invoke, state, config=…)
  │  On failure: log redacted stack once → safe HTTP detail
  ▼
edim-dde-ai MetadataAgent
  │  Wrap flat state → LangGraph data bag
  │  LangSmith run tags: agent_id, env, request_id
  ▼
YAML graph nodes
  │  domain.sql.query → sources.resolve → auth token → warehouse → UC Delta
  │  domain.tuning.*  → sizing / guardrails / risk
  │  llm_chain        → ContentHub prompts + Foundry
  │  (optional) invoke_agent → nested agent with depth limit
  ▼
Response projection
  │  Map agent state → TuningResponse / RcaResponse (never dump full state)
  ▼
Client + LangSmith (trace retained per project retention)
```

---

## 5. Environments (current focus)

Full set later: **SDBX, DEV, UAT, INTG, PROD**.  
**Current focus:** SDBX, DEV, PROD — see [environments.md](../platform/environments.md).

| Env | Purpose | LangSmith project (convention) |
|-----|---------|--------------------------------|
| SDBX | Sandbox / spikes | `edim-dde-sdbx` |
| DEV | Active development | `edim-dde-dev` (App: `edim-dde-api-dev`) |
| PROD | Production | `edim-dde-prod` (App: `edim-dde-api-prod`) |

---

## 6. Security stance (R1)

| Control | R1 behavior |
|---------|-------------|
| YAML code execution | **Denied** — node/router types must be pre-registered |
| SQL identity (**U**) | Apps user OAuth + scope `sql`, or local Azure AD |
| LLM identity (**B**) | `EDIM_FOUNDRY_*` (not `AZURE_CLIENT_*`) |
| Vault opener (**A**) | Apps SP (`DATABRICKS_CLIENT_*` + `AZURE_TENANT_ID`) → Key Vault |
| Secrets | Azure Key Vault SDK; map `ENV_VAR:vaultSecret` into process env |
| PII | Expandable redaction patterns (SSN, PAN, account, member id) before logs/traces |
| Roles | Documented matrix; **not enforced** yet beyond identity above |

Details: [security-baseline.md](../platform/security-baseline.md), [pii-guardrails.md](../platform/pii-guardrails.md).

---

## 7. Observability (LangSmith)

R1 documents setup and wires optional tracing. Full eval/CI comes later.

Guide: [langsmith-setup.md](../platform/langsmith-setup.md) · [observability.md](../platform/observability.md).

---

## 8. Control-plane state store

Pluggable `StateStore` for catalog metadata, sessions, and audit — **not** a replacement for Azure DevOps `*.agent.yaml`.

| Env | Typical backend |
|-----|-----------------|
| Local / SDBX / DEV | `EDIM_STATE_STORE=postgres` (Docker Compose) |
| Deployed Apps / PROD | `EDIM_STATE_STORE=cosmos` |
| Tests / demos | `memory` (default) |

On API start: `configure_state_store_from_env()` → `bootstrap_agents()` → `sync_registered_agents_to_store()`.

Full guide: [state-store.md](../platform/state-store.md).

---

## 9. Retrieval & RAG (knowledge plane)

Pluggable `RetrievalProvider` for similarity / hybrid search. **RAG** = retrieve + LLM in the agent graph (pilot: `spark_rca` runbooks).

| Env | Typical backend |
|-----|-----------------|
| Local / Volume | `EDIM_RETRIEVAL=faiss` + `EDIM_FAISS_INDEX_PATH` |
| Deployed default | `EDIM_RETRIEVAL=azure_ai_search` |
| Lakehouse corpus override | `databricks_vector` per corpus in `corpora.yaml` |

R1 non-goals above still defer full enterprise RAG platform / retention — this section is the **framework spike** toward BL-021.

Full guide: [retrieval-and-rag.md](../platform/retrieval-and-rag.md).

---

## Related docs

- [Architecture overview](overview.md)
- [Packages](packages.md)
- [Auth and SQL](auth-and-sql.md)
- [Config → observability flow](config-to-observability.md)
- [Control-plane state store](../platform/state-store.md)
- [Retrieval & RAG](../platform/retrieval-and-rag.md)
- [YAML schema contract](../framework/yaml-schema.md)
- [Orchestration topology](../framework/orchestration-topology.md)

## Summary

- R1 reference architecture is the signed-off map of packages, planes, and non-goals.
- Use companion SVGs and the HTML deck for reviews; deep ops live in platform/framework chapters.

**Next →** [Architecture deck (B5)](architecture-deck.md)

<!-- edim-learning-nav -->
---

← [Packages](packages.md) · [Preface](../README.md) · [Architecture deck](architecture-deck.md) →
