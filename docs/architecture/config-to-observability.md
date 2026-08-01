# Config → runtime → observability flow (BL-003)

End-to-end path from agent YAML on disk to HTTP response and LangSmith.

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
│ + LangSmith tags │  agent_id, env, request_id
└────────┬─────────┘
         │ LangGraph node execution
         ├─ domain.sql.query ──► Databricks SQL / UC
         ├─ domain.* logic
         ├─ llm_chain ──► Foundry (Azure OpenAI)
         └─ invoke_agent ──► nested agent (depth-limited)
         ▼
┌──────────────────┐     dashed     ┌────────────────┐
│ API DTO response │───────────────►│ LangSmith      │
│ (projected)      │   side channel │ project / env   │
└──────────────────┘                └────────────────┘
```

## Correlation

| Field | Source | Purpose |
|-------|--------|---------|
| `request_id` | `X-Request-Id` header or generated UUID | Tie API call ↔ LangSmith run |
| `EDIM_ENV` | Environment variable | Tag runs per SDBX/DEV/PROD |
| `agent_id` | Agent definition | Filter traces by agent |

## Operator steps

1. Validate YAML / schema locally
2. Start API with env + optional Key Vault bootstrap
3. Invoke endpoint
4. Open LangSmith project for that env — see [langsmith-setup.md](../platform/langsmith-setup.md)

## Related

- [Request flow](request-flow.md)
- [Reference architecture](reference-architecture.md)
- [YAML schema](../framework/yaml-schema.md)
