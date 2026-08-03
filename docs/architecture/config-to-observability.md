# Config → runtime → observability flow (BL-003)

End-to-end path from agent YAML on disk to HTTP response and the active observability backend (LangSmith, MLflow, or none).

```text
┌──────────────────┐
│ *.agent.yaml     │  schema-validated (edim-dde-ai)
│ content/prompts  │
└────────┬─────────┘
         │ bootstrap_agents() / register_from_yaml
         ▼
┌──────────────────┐
│ Registries       │  agents · nodes · routers · chains · content
└────────┬─────────┘
         │ create_agent(agent_id)  → compile once, cache
         ▼
┌──────────────────┐
│ MetadataAgent    │  flat dict in/out
│ ObservabilityProvider │  EDIM_OBSERVABILITY → langsmith | mlflow | none
│ + correlation    │  agent_id, env, request_id
└────────┬─────────┘
         │ LangGraph node execution
         ├─ domain.sql.query ──► Databricks SQL / UC
         ├─ domain.* logic
         ├─ llm_chain ──► Foundry (Azure OpenAI)
         └─ invoke_agent ──► nested agent (depth-limited)
         ▼
┌──────────────────┐     dashed     ┌────────────────────────────┐
│ API DTO response │───────────────►│ LangSmith and/or MLflow    │
│ (projected)      │   side channel │ (whichever provider is set) │
└──────────────────┘                └────────────────────────────┘
```

## Selecting a backend

```bash
EDIM_OBSERVABILITY=langsmith   # recommended R1 default when tracing
# EDIM_OBSERVABILITY=mlflow
# EDIM_OBSERVABILITY=none
```

See [observability providers](../platform/observability.md).

## Correlation

| Field | Source | Purpose |
|-------|--------|---------|
| `request_id` | `X-Request-Id` header or generated UUID | Tie API call ↔ backend run |
| `EDIM_ENV` | Environment variable | Tag runs per SDBX/DEV/PROD |
| `agent_id` | Agent definition | Filter traces by agent |

## Operator steps

1. Validate YAML / schema locally
2. Start API with env + optional Key Vault bootstrap + `EDIM_OBSERVABILITY`
3. Invoke endpoint
4. Open the backend UI for that env — [LangSmith setup](../platform/langsmith-setup.md) or your MLflow tracking UI

## Related

- [Request flow](request-flow.md)
- [Reference architecture](reference-architecture.md)
- [Observability providers](../platform/observability.md)
- [YAML schema](../framework/yaml-schema.md)
