# Architecture overview

```text
Client (curl / future UI / Databricks Apps)
        │
        ▼
edim-dde-api  (v1.0.0)
  • CORS (EDIM_CORS_ORIGINS)
  • DatabricksUserTokenMiddleware  (X-Forwarded-Access-Token → ContextVar)
  • Key Vault secret bootstrap (optional)
  • lifespan: bootstrap_agents() + set_llm_provider(Foundry lazy)
  • GET  /health
  • POST /api/v1/recommendations  → cluster_tuning
  • POST /api/v1/rca/analyze      → spark_rca
        │
        ▼
edim-dde-ai  (v1.0.0)
  • create_agent(id)  (compiled graph cached)
  • LangGraph from *.agent.yaml (+ schema contract)
  • llm_chain → ContentHub + LLMProvider
  • invoke_agent → nested agent (depth-limited)
  • LangSmith tags (agent_id, env, request_id)
        │
        ├─ domain.sql.query ──► sources + auth ──► Databricks SQL / UC
        └─ domain.tuning.* / domain.rca.* ──► agent logic + helpers
```

**Design rule:** collect data with declarative SQL in YAML + one generic `domain.sql.query` node. No per-use-case SQL collector classes.

**Presentation / sign-off:** [Reference architecture](reference-architecture.md) · [HTML deck](diagrams/r1-architecture-deck.html)

See also [packages](packages.md), [auth and SQL](auth-and-sql.md), [request flow](request-flow.md), [config → observability](config-to-observability.md).
