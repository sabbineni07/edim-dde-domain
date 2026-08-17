# Packages (B3)

**Learning path:** B3 · [Guide home](../README.md)  
**← Previous:** [Architecture overview](overview.md) · **Next:** [Reference architecture](reference-architecture.md) →

Ownership boundaries — keep dependencies one-way.

**One-line contract (use in reviews / slides):**

> **ai** = reusable agent runtime (graphs, scoring hooks, stores, traces).  
> **domain** = Databricks + product semantics (SQL/UC, Foundry, tuning & RCA).  
> **api** = thin HTTP host.

---

## Responsibility matrix

| Package | Responsibility | Does *not* own |
|---------|----------------|----------------|
| **edim-dde-ai** | YAML parse, registries, graph build, builtins (`llm_chain`, `invoke_agent`, `rag.retrieve`), ObservabilityProvider, StateStore, RetrievalProvider | Product SQL, Databricks auth, HTTP |
| **edim-dde-domain** | Sources, SQL execute, Apps/`az` auth, Foundry adapter, bundled agents, corpora/runbooks, plugin loader | HTTP routes, OpenAPI response projection |
| **edim-dde-api** | FastAPI, middleware (`RequestId`, Apps token), v1 routes (incl. knowledge ingest), lifespan (KV + observability + state store + retrieval + catalog sync), response models, safe boundary logging | Agent business logic |

```text
edim-dde-api  →  edim-dde-domain  →  edim-dde-ai
```

External agent plugins depend on `edim-dde-ai` (and usually domain for `domain.sql.query` / sources) and register via [external plugins](../build-agents/external-plugins.md).

---

## Pattern placement

| Concern | Package | Pattern |
|---------|---------|---------|
| Node/router/agent catalogs | ai | Registry + Strategy |
| Graph assembly | ai | Builder |
| Flat state ↔ LangGraph | ai | Adapter |
| Invoke surface | ai | Template Method + Facade |
| Postgres/Cosmos/FAISS/… | ai protocols; domain/api wire env | Strategy |
| SQL sources + Foundry | domain | Adapter (warehouse / LLM) |
| HTTP DTOs | api | Facade over agents |

---

## Module map (`edim-dde-ai`)

```text
edim_dde_ai/
  core/            definition + YAML load
  registry/        agents, nodes, chains, routers
  graph/           builder, adapters, MetadataAgent
  nodes/           builtins including rag.retrieve
  content/         prompts, skills, LLMProvider
  observability/   ObservabilityProvider
  store/           StateStore (+ connection_env shared with recommendations)
  recommendations/ RecommendationStore (product history)
  retrieval/       RetrievalProvider
  api/             register_from_*
```

Domain deep dive: [Sources & SQL design](../DESIGN_SOURCES_AND_SQL_NODES.md).  
Framework deep dive: `edim-dde-ai/docs/DESIGN.md`.

---

← [Overview](overview.md) · [Guide home](../README.md) · [Reference architecture](reference-architecture.md) →
