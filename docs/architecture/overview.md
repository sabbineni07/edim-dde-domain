# Architecture overview

```text
Client (curl / future UI / Databricks Apps)
        │
        ▼
edim-dde-api  (v1.0.0)
  • CORS (EDIM_CORS_ORIGINS)
  • DatabricksUserTokenMiddleware
  • Key Vault secret bootstrap (optional)
  • ObservabilityProvider (LangSmith / MLflow / none)
  • StateStore (memory / postgres / cosmos / redis)  ← control plane
  • RetrievalProvider (faiss / azure / databricks / …) ← knowledge
  • lifespan: bootstrap_agents() + sync catalog + Foundry lazy
  • GET  /health
  • POST /api/v1/recommendations  → cluster_tuning
  • POST /api/v1/rca/analyze      → spark_rca (+ runbook RAG)
  • POST /api/v1/knowledge/ingest → curated upsert (Acceptance-gated)
        │
        ▼
edim-dde-ai  (v1.0.0)
  • create_agent(id)  (compiled graph cached)
  • LangGraph from *.agent.yaml (+ schema contract)
  • llm_chain · invoke_agent · rag.retrieve
  • LangSmith / MLflow hooks via ObservabilityProvider
  • StateStore sync (agent metadata, sessions, audit)
  • RetrievalProvider (similarity search backends)
        │
        ├─ domain.sql.query ──► Databricks SQL / UC          (data plane)
        ├─ domain.tuning.* / domain.rca.* + Foundry          (data plane)
        ├─ rag.retrieve ──► FAISS / Azure AI Search / DBX VS (knowledge)
        └─ StateStore ──► Postgres (local) / Cosmos (deploy) (control plane)
```

**Planes**

| Plane | Responsibility |
|-------|----------------|
| **Source control** | Azure DevOps / Git — `*.agent.yaml`, prompts, runbooks, CI |
| **Control plane** | StateStore — catalog metadata, sessions, audit |
| **Knowledge / retrieval** | RetrievalProvider — similarity search indexes (not StateStore) |
| **Data plane** | LangGraph + Databricks + Foundry — do the work |
| **Observability** | LangSmith / MLflow — traces and eval |

**Design rule:** collect data with declarative SQL in YAML + one generic `domain.sql.query` node. No per-use-case SQL collector classes.

**Git vs store vs index:** Agent *graphs* stay in Azure DevOps. StateStore holds *catalog metadata*. Vector/keyword indexes hold *knowledge chunks* — see [state-store.md](../platform/state-store.md) and [retrieval-and-rag.md](../platform/retrieval-and-rag.md).

**Presentation / sign-off:** [Reference architecture](reference-architecture.md) · [HTML deck](diagrams/r1-architecture-deck.html)

See also [packages](packages.md), [auth and SQL](auth-and-sql.md), [request flow](request-flow.md), [config → observability](config-to-observability.md).
