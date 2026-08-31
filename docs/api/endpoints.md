# HTTP endpoints

**Learning path:** G2 · [Preface](../README.md)  
**← Previous:** [Configuration](configuration.md) · **Next:** [Deploy & hosting](deploy-and-hosting.md) →

## Chapter summary

HTTP surface of `edim_dde_api.main:app`: health, tuning/RCA recommend routes, recommendation history, knowledge ingest, and debug helpers. Request/response shapes stay in the API models.

**Outcome:** you know which path to call for each product capability.

---

Base app: `edim_dde_api.main:app`

| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | `/health` | — | `{status, agents, version, observability, state_store, conversation_store, recommendation_store, retrieval, web_search}` |
| POST | `/api/v1/cluster_tuning/recommend` | `TuningRequest` | `TuningResponse` |
| GET | `/api/v1/cluster_tuning/recommendations` | query filters | `list[RecommendationHistoryItem]` |
| GET | `/api/v1/cluster_tuning/recommendations/{id}` | — | `RecommendationHistoryItem` |
| PATCH | `/api/v1/cluster_tuning/recommendations/{id}` | `RecommendationStatusUpdate` | `RecommendationHistoryItem` |
| POST | `/api/v1/rca/analyze` | `RcaRequest` | `RcaResponse` |
| GET | `/api/v1/rca/recommendations` | query filters | `list[RecommendationHistoryItem]` |
| GET | `/api/v1/rca/recommendations/{id}` | — | `RecommendationHistoryItem` |
| PATCH | `/api/v1/rca/recommendations/{id}` | `RecommendationStatusUpdate` | `RecommendationHistoryItem` |
| POST | `/api/v1/knowledge/ingest` | `KnowledgeIngestRequest` | `KnowledgeIngestResponse` |
| GET | `/api/v1/debug/sql-auth` | — | Booleans only (Apps SQL auth diagnostics; no tokens) |
| POST | `/api/v1/sessions` | `{agent_id, state}` | `SessionResponse` (`waiting_hitl` or `completed`) |
| GET | `/api/v1/sessions/{session_id}` | — | `SessionResponse` |
| POST | `/api/v1/sessions/{session_id}/resume` | `{decision, comment?, patch?}` | `SessionResponse` (`closed` or paused again) |

HITL details: [HITL resume](../framework/hitl-resume.md) (YAML, HTTP, GoF map, why `HitlPaused` is not an error). Demo agent: `hitl_demo`. Product routes do not pause unless those graphs add a `hitl.gate`.

OpenAPI: `http://localhost:8080/docs` when uvicorn is running.

**Breaking (hard cutover):** `/api/v1/recommendations` and unversioned `/api/recommendations` are **not** registered — use `/api/v1/cluster_tuning/recommend`.

Response models project agent state explicitly (RCA requires `result`; no full-state fallback). Memory-enabled RCA and tuning responses include a `conversation_id`; send it back with an optional `message` to ask a follow-up question. The framework applies the agent's YAML memory policy before LLM calls; omitted memory defaults to `strategy: none`. Conversation memory is separate from HITL sessions and RecommendationStore product history. RCA responses may include richer fields (`job_status`, `evidence_analysis`, structured `recommendations`, cited `evidence`, `request_id`, …). `evidence` rows carry a `backfilled` flag and the response sets `evidence_backfilled`: when the model cites nothing resolvable these are labeled pack-preview rows, not model citations (see the [Spark-RCA agent guide](../domain/spark-rca-agent.md#step-n--validate_output)).

### Conversational follow-ups

The bundled `spark_rca` and `cluster_tuning` agents accept:

```json
{
  "conversation_id": "<id returned by an earlier response>",
  "message": "Can we reduce the worker count further?"
}
```

Include the required job identity and evidence/metrics fields as usual. For an
agent with an enabled memory strategy, a new conversation is created when
`conversation_id` is omitted. The `message` is stored in the separate
conversation-memory store and is added to the current LLM request; it is not
written to RCA/tuning product history.

Agents with `strategy: none` run without conversation history and do not return
a `conversation_id`. A `message` is still accepted as a standalone question,
but supplying a `conversation_id` returns HTTP `422` because the agent cannot
evaluate that follow-up with its prior context.

### Cluster tuning — guardrail retries

When the sizing LLM output violates policy (workers, vCPUs, auto-termination, …), the agent **re-prompts once** with `guardrail_feedback` (max **2** sizing LLM calls). Deterministic SKU mapping alone does not trigger a retry.

| Response field | Meaning |
|----------------|---------|
| `sizing_attempts` | How many sizing LLM calls ran (1 or 2) |
| `guardrail_retries` | Re-prompts after the first call (`sizing_attempts - 1`) |
| `guardrail_adjustments` | Final clamps still applied after the last attempt (may be empty or SKU-only) |

### Cluster tuning — performance validation

After sizing settles, a **rule-based** `validate_performance` node checks whether recommended capacity (vCPU × max workers) is likely to meet peak load (legacy parity; no LLM). Result is projected as `performance_validation` and folded into `risk_assessment` / reason codes when it fails.

| Field | Meaning |
|-------|---------|
| `meets_peak_requirements` | Pass/fail fitness |
| `estimated_impact` | `maintained` or `degradation_risk` |
| `reduction_pct` | Capacity cut vs current |
| `reasons` | Which checks failed (if any) |

### Cluster tuning — recommendation history

Successful recommends are **best-effort** persisted via pluggable `RecommendationStore` (default inherits `EDIM_STATE_STORE`). See [recommendation-store.md](../platform/recommendation-store.md).

| Field / route | Meaning |
|---------------|---------|
| `recommendation_id` / `recommendation_status` | Set on tuning and RCA responses when persist succeeds |
| `GET …/cluster_tuning/recommendations` | List newest-first (`job_id`, `cluster_id`, `status`, `limit`) |
| `PATCH …/recommendations/{id}` | Lifecycle: `proposed` \| `accepted` \| `rejected` \| `applied` \| `superseded` |
| `GET …/rca/recommendations` | RCA history newest-first (`job_id`, `status`, `limit`) |

### Request id / logging

| Behavior | Detail |
|----------|--------|
| Header | Optional `X-Request-Id`; if omitted the API generates a UUID |
| Response | Same id echoed as `X-Request-Id` response header (and on RCA/tuning bodies when projected) |
| Server logs | Stdlib lines include `[request_id=…]` via `RequestIdMiddleware` + logging filter |
| Failures | Original exception + stack logged **once** at the HTTP boundary; secrets/tokens/PII redacted; HTTP `detail` stays short/safe |

See [request flow](../architecture/request-flow.md) · [config → observability](../architecture/config-to-observability.md).

### Knowledge ingest

Curated upsert into the active `RetrievalProvider`. Requires `accepted: true`. Optional `summary` is prepended to `text`. Bulk indexing remains platform Jobs — see [retrieval-and-rag.md](../platform/retrieval-and-rag.md).

## Summary

- Health reports plane backends; recommend routes invoke bundled agents.
- Knowledge ingest is curated and Acceptance-gated; bulk index stays in Jobs.

**Next →** [Deploy & hosting](deploy-and-hosting.md)

<!-- edim-learning-nav -->
---

← [Configuration](configuration.md) · [Preface](../README.md) · [Deploy & hosting](deploy-and-hosting.md) →
