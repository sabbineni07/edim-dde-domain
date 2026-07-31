# HTTP endpoints

Base app: `edim_dde_api.main:app`

| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | `/health` | — | `{status, agents}` |
| POST | `/api/v1/recommendations` | `TuningRequest` | `TuningResponse` |
| POST | `/api/v1/rca/analyze` | `RcaRequest` | `RcaResponse` |

OpenAPI: `http://localhost:8080/docs` when uvicorn is running.

Unversioned `/api/recommendations` and `/api/rca/analyze` are **not** registered.

Response models project agent state explicitly (RCA requires `result`; no full-state fallback).
