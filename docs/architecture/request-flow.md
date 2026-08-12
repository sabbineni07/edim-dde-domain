# Request flow

**Learning path:** B6 · [Guide home](../README.md)
**← Previous:** [Architecture deck](architecture-deck.md) · **Next:** [Auth and SQL](auth-and-sql.md) →


Lifecycle of a typical `POST /api/v1/cluster_tuning/recommend` call (similar idea to documenting job state machines such as [EMR Serverless job states](https://docs.aws.amazon.com/emr/latest/EMR-Serverless-UserGuide/job-states.html)):

```text
1. HTTP request
   └─ Pydantic TuningRequest validates body
   └─ Optional X-Request-Id (else generated)

2. Middleware / lifespan
   └─ RequestIdMiddleware: bind request_id for logs; echo X-Request-Id on response
   └─ Optional X-Forwarded-Access-Token → request-scoped Databricks token
   └─ At startup (once): Key Vault → observability → StateStore → bootstrap → catalog sync
      (startup failures: log redacted stack once, continue with safe defaults when possible)

3. Route (async)
   └─ build_run_config(agent_id, request_id) for LangSmith tags
   └─ Re-bind request_id (+ Apps token) inside asyncio.to_thread worker
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
   └─ Stdlib logs: [request_id=…] on each line for this call

6. Response projection
   └─ tuning_response_from_agent_state(final) → TuningResponse
      (never return the full agent state bag)
   └─ On failure: log original stack once (secrets/PII redacted) → safe HTTP detail
```

RCA is the same pattern with `spark_rca` and `RcaResponse` (requires `result` in agent state). After classify, RCA builds a retrieval query and calls `rag.retrieve` for runbook grounding before the LLM.

**Failure mapping (API):**

| Condition | HTTP | Logging |
|-----------|------|---------|
| No metrics rows (`NoJobMetricsError`) | 404 | WARNING + redacted stack (once) |
| Warehouse / auth not configured | 503 | WARNING + redacted stack (once) |
| Domain/SQL tool failure | 502 | ERROR + redacted stack (once) |
| Foundry not configured / chain error | 503 | Handler logs once (not duplicated in route) |
| RCA missing `result` | 500 | ERROR + redacted stack (once) |
| Knowledge ingest without `accepted=true` | 400 | No stack (validation) |
| Knowledge ingest backend unsupported | 501 | WARNING + redacted stack (once) |

Client `detail` / `error_code` stay short and safe — **do not** expect stack traces in JSON. Use `X-Request-Id` to find the matching server log block.

See also [config → observability](config-to-observability.md), [state store](../platform/state-store.md), [retrieval & RAG](../platform/retrieval-and-rag.md), and [LangSmith setup](../platform/langsmith-setup.md).

<!-- edim-learning-nav -->
---

← [Architecture deck](architecture-deck.md) · [Guide home](../README.md) · [Auth and SQL](auth-and-sql.md) →
