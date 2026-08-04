# Request flow

Lifecycle of a typical `POST /api/v1/recommendations` call (similar idea to documenting job state machines such as [EMR Serverless job states](https://docs.aws.amazon.com/emr/latest/EMR-Serverless-UserGuide/job-states.html)):

```text
1. HTTP request
   └─ Pydantic TuningRequest validates body
   └─ Optional X-Request-Id (else generated)

2. Middleware / lifespan
   └─ Optional X-Forwarded-Access-Token → request-scoped Databricks token
   └─ At startup (once): Key Vault → observability → StateStore → bootstrap → catalog sync

3. Route (async)
   └─ build_run_config(agent_id, request_id) for LangSmith tags
   └─ asyncio.to_thread(create_agent("cluster_tuning").invoke, …)

4. Framework
   └─ Cached MetadataAgent → LangGraph nodes in YAML order
        • domain.sql.query (or skip if metrics override present)
        • domain.tuning.* logic nodes
        • llm_chain (sizing / explanation) when configured
        • optional invoke_agent nested calls

5. Side channels
   └─ Observability: LangSmith / MLflow when configured
   └─ Control plane: StateStore already holds catalog metadata (not on every request)
   └─ Knowledge: rag.retrieve on spark_rca (optional; empty if EDIM_RETRIEVAL=none)

6. Response projection
   └─ tuning_response_from_agent_state(final) → TuningResponse
      (never return the full agent state bag)
```

RCA is the same pattern with `spark_rca` and `RcaResponse` (requires `result` in agent state). After classify, RCA builds a retrieval query and calls `rag.retrieve` for runbook grounding before the LLM.

**Failure mapping (API):**

| Condition | HTTP |
|-----------|------|
| No metrics rows (`NoJobMetricsError`) | 404 |
| Warehouse / auth not configured | 503 |
| Foundry not configured / chain error | 503 |
| RCA missing `result` | 500 |
| Knowledge ingest without `accepted=true` | 400 |
| Knowledge ingest backend unsupported | 501 |

See also [config → observability](config-to-observability.md), [state store](../platform/state-store.md), [retrieval & RAG](../platform/retrieval-and-rag.md), and [LangSmith setup](../platform/langsmith-setup.md).