# Architecture overview (B2)

**Learning path:** B2 · [Preface](../README.md)  
**← Previous:** [End-to-end design (B1)](end-to-end-design.md) · **Next:** [Packages (B3)](packages.md) →

## Chapter summary

A **one-page system sketch** of the three-package stack and plane boundaries.
For deployment selection, packaging, and rollout detail, read
**[Deployment targets and release runbook](../api/deployment-targets.md)**. For
patterns, lifecycle detail, and invariants, read **[End-to-end design
(B1)](end-to-end-design.md)** first.

---

## System sketch

```text
Client (curl / future UI / Databricks Apps / APIM)
        │
        ▼
ACA Native: edim-dde-api  (v1.0.0)
  • CORS (EDIM_CORS_ORIGINS)
  • DatabricksUserTokenMiddleware
  • Key Vault secret bootstrap (optional)
  • ObservabilityProvider (Azure-native / LangSmith / MLflow / none)
  • StateStore (memory / postgres / cosmos / redis)  ← control plane
  • RetrievalProvider (faiss / azure / databricks / …) ← knowledge
  • lifespan: bootstrap_agents() + sync catalog + Foundry lazy
  • GET  /health
  • POST /api/v1/cluster_tuning/recommend  → cluster_tuning
  • POST /api/v1/rca/analyze      → spark_rca (+ runbook RAG)
  • POST /api/v1/knowledge/ingest → curated upsert (Acceptance-gated)
        │
        ▼
edim-dde-ai  (v1.0.0)
  • create_agent(id)  (compiled graph cached)
  • LangGraph from *.agent.yaml (+ schema contract)
  • llm_chain · invoke_agent · rag.retrieve
  • ObservabilityProvider · StateStore · RetrievalProvider
        │
        ├─ domain.sql.query ──► Databricks SQL / UC          (data plane)
        ├─ domain.tuning.* / domain.rca.* + Foundry          (data plane)
        ├─ rag.retrieve ──► FAISS / Azure AI Search / DBX VS (knowledge)
        └─ StateStore ──► Postgres (local) / Cosmos (deploy) (control plane)
```

The same YAML graph package can instead be loaded by the optional Standalone
Agent Server on ACA or by Full self-hosted LangSmith Deployment on AKS. Those
targets change the runtime API and platform resources; they do not change the
agent topology or domain rules.

---

## Planes

| Plane | Responsibility |
|-------|----------------|
| **Source control** | Azure DevOps / Git — `*.agent.yaml`, prompts, runbooks, CI |
| **Control plane** | StateStore — catalog metadata, sessions, audit. **Later (parked):** same plane may add location/policy/routing — not a new plane. [B9b](agent-control-plane.md) |
| **Knowledge / retrieval** | RetrievalProvider — similarity search indexes (not StateStore) |
| **Data plane** | LangGraph + Databricks + Foundry — do the work |
| **Observability** | LangSmith / MLflow — traces and eval |
| **Ingest (batch)** | Platform Jobs (+ curated API) — write indexes |

**Design rule:** collect telemetry with declarative SQL in YAML + one generic `domain.sql.query` node. No per-use-case SQL collector classes.

**Git vs store vs index:** Agent *graphs* stay in Azure DevOps. StateStore holds *catalog metadata*. Vector/keyword indexes hold *knowledge chunks*.

---

## Presentation

- [Reference architecture](reference-architecture.md) · [Architecture deck](architecture-deck.md)
- SVGs: [context](diagrams/r1-system-context.svg) · [sequence](diagrams/r1-request-sequence.svg) · [envs](diagrams/r1-environments.svg)

---

← [End-to-end design](end-to-end-design.md) · [Preface](../README.md) · [Packages](packages.md) →
