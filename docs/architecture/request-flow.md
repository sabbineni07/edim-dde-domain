# Request flow

Lifecycle of a typical `POST /api/v1/recommendations` call (similar idea to documenting job state machines such as [EMR Serverless job states](https://docs.aws.amazon.com/emr/latest/EMR-Serverless-UserGuide/job-states.html)):

```text
1. HTTP request
   └─ Pydantic TuningRequest validates body

2. Middleware
   └─ Optional X-Forwarded-Access-Token → request-scoped Databricks token

3. Route (async)
   └─ asyncio.to_thread(create_agent("cluster_tuning").invoke, state)

4. Framework
   └─ Cached MetadataAgent → LangGraph nodes in YAML order
        • domain.sql.query (or skip if metrics override present)
        • domain.tuning.* logic nodes
        • llm_chain (sizing / explanation) when configured

5. Response projection
   └─ tuning_response_from_agent_state(final) → TuningResponse
      (never return the full agent state bag)
```

RCA is the same pattern with `spark_rca` and `RcaResponse` (requires `result` in agent state).

**Failure mapping (API):**

| Condition | HTTP |
|-----------|------|
| No metrics rows (`NoJobMetricsError`) | 404 |
| Warehouse / auth not configured | 503 |
| Foundry not configured / chain error | 503 |
| RCA missing `result` | 500 |
