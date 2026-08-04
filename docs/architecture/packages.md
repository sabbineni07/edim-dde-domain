# Packages

| Package | Responsibility | Does *not* own |
|---------|----------------|----------------|
| **edim-dde-ai** | YAML parse, registries, graph build, builtins (`llm_chain`, `invoke_agent`, `rag.retrieve`), ObservabilityProvider, StateStore, **RetrievalProvider** | Product SQL, Databricks auth, HTTP |
| **edim-dde-domain** | Sources, SQL execute, Apps/`az` auth, Foundry adapter, bundled agents, corpora/runbooks, plugin loader | HTTP routes, OpenAPI response projection |
| **edim-dde-api** | FastAPI, middleware, v1 routes (incl. knowledge ingest), lifespan (KV + observability + state store + retrieval + catalog sync), response models | Agent business logic |

Dependency direction:

```text
edim-dde-api  →  edim-dde-domain  →  edim-dde-ai
```

External agent plugins depend on `edim-dde-ai` (and usually domain for `domain.sql.query` / sources) and register via [external plugins](../build-agents/external-plugins.md).
