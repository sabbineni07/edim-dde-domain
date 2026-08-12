# HTTP endpoints

**Learning path:** G2 · [Guide home](../README.md)
**← Previous:** [Configuration](configuration.md) · **Next:** [Deploy & hosting](deploy-and-hosting.md) →


Base app: `edim_dde_api.main:app`

| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | `/health` | — | `{status, agents, version, observability, state_store, retrieval}` |
| POST | `/api/v1/cluster_tuning/recommend` | `TuningRequest` | `TuningResponse` |
| POST | `/api/v1/rca/analyze` | `RcaRequest` | `RcaResponse` |
| POST | `/api/v1/knowledge/ingest` | `KnowledgeIngestRequest` | `KnowledgeIngestResponse` |
| GET | `/api/v1/debug/sql-auth` | — | Booleans only (Apps SQL auth diagnostics; no tokens) |

OpenAPI: `http://localhost:8080/docs` when uvicorn is running.

**Breaking (hard cutover):** `/api/v1/recommendations` and unversioned `/api/recommendations` are **not** registered — use `/api/v1/cluster_tuning/recommend`.

Response models project agent state explicitly (RCA requires `result`; no full-state fallback). RCA responses may include richer fields (`job_status`, `evidence_analysis`, structured `recommendations`, cited `evidence`, `request_id`, …).

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

<!-- edim-learning-nav -->
---

← [Configuration](configuration.md) · [Guide home](../README.md) · [Deploy & hosting](deploy-and-hosting.md) →
