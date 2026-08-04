# HTTP endpoints

**Learning path:** G2 · [Guide home](../README.md)
**← Previous:** [Configuration](configuration.md) · **Next:** [Environment variables](../reference/env-vars.md) →


Base app: `edim_dde_api.main:app`

| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | `/health` | — | `{status, agents, version, observability, state_store, retrieval}` |
| POST | `/api/v1/recommendations` | `TuningRequest` | `TuningResponse` |
| POST | `/api/v1/rca/analyze` | `RcaRequest` | `RcaResponse` |
| POST | `/api/v1/knowledge/ingest` | `KnowledgeIngestRequest` | `KnowledgeIngestResponse` |

OpenAPI: `http://localhost:8080/docs` when uvicorn is running.

Unversioned `/api/recommendations` and `/api/rca/analyze` are **not** registered.

Response models project agent state explicitly (RCA requires `result`; no full-state fallback).

### Knowledge ingest

Curated upsert into the active `RetrievalProvider`. Requires `accepted: true`. Optional `summary` is prepended to `text`. Bulk indexing remains platform Jobs — see [retrieval-and-rag.md](../platform/retrieval-and-rag.md).

<!-- edim-learning-nav -->
---

← [Configuration](configuration.md) · [Guide home](../README.md) · [Environment variables](../reference/env-vars.md) →
