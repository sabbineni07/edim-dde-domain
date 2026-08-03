# Packages

| Package | Responsibility | Does *not* own |
|---------|----------------|----------------|
| **edim-dde-ai** | YAML parse, registries, graph build, builtins, content hub, ObservabilityProvider, **StateStore** | Product SQL, Databricks auth, HTTP |
| **edim-dde-domain** | Sources, SQL execute, Apps/`az` auth, Foundry adapter, bundled agents, plugin loader | HTTP routes, OpenAPI response projection |
| **edim-dde-api** | FastAPI, middleware, v1 routes, lifespan (KV + observability + state store + catalog sync), response models | Agent business logic |

Dependency direction:

```text
edim-dde-api  →  edim-dde-domain  →  edim-dde-ai
```

External agent plugins depend on `edim-dde-ai` (and usually domain for `domain.sql.query` / sources) and register via [external plugins](../build-agents/external-plugins.md).
