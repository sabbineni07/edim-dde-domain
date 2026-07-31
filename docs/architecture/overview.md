# Architecture overview

```text
Client (curl / future UI / Databricks Apps)
        │
        ▼
edim-dde-api
  • CORS (EDIM_CORS_ORIGINS)
  • DatabricksUserTokenMiddleware  (X-Forwarded-Access-Token → ContextVar)
  • lifespan: bootstrap_agents() + set_llm_provider(Foundry lazy)
  • GET  /health
  • POST /api/v1/recommendations  → cluster_tuning
  • POST /api/v1/rca/analyze      → spark_rca
        │
        ▼
edim-dde-ai
  • create_agent(id)  (compiled graph cached)
  • LangGraph from *.agent.yaml
  • llm_chain → ContentHub + LLMProvider
        │
        ├─ domain.sql.query ──► sources + auth ──► Databricks SQL / UC
        └─ domain.tuning.* / domain.rca.* ──► agent logic + helpers
```

**Design rule:** collect data with declarative SQL in YAML + one generic `domain.sql.query` node. No per-use-case SQL collector classes.

See also [packages](packages.md), [auth and SQL](auth-and-sql.md), [request flow](request-flow.md).
