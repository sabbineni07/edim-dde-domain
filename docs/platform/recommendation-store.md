# Recommendation lifecycle store (Postgres · Cosmos · Redis · memory · none)

**Learning path:** C6b · [Guide home](../README.md)
**← Previous:** [Control-plane state store](state-store.md) · **Next:** [Retrieval & RAG](retrieval-and-rag.md) →

---

## 1. Why a separate store?

`StateStore` is the **control plane** (agent catalog, sessions, audit).  
`RecommendationStore` is **product history** — persist cluster-tuning (and future) recommendations beyond a single HTTP response, with lifecycle status:

`proposed` → `accepted` | `rejected` | `applied` | `superseded`

Same **Strategy + Factory + Registry** pattern as StateStore / Observability / Retrieval — plug-and-play backends, one process-wide instance.

**Derived experience index:** `set_recommendation_store` wraps backends in `ExperienceIndexingStore` so each `save` / `update_status` also upserts (or deletes) a situation/action card into the active `RetrievalProvider` corpus (see [Retrieval & RAG §6c](retrieval-and-rag.md#6c-experience-index-platform--all-future-agents)). The store remains the system of record; vectors are a derived view for **feature** similarity across jobs.

```text
┌─────────────────────────────────────────────────────────────────┐
│  RecommendationStore (product history)                          │
│  Backends: none | memory | postgres | cosmos | redis            │
│  Shares connection env with StateStore (DSN / Cosmos / Redis)   │
└─────────────────────────────────────────────────────────────────┘
```

| Concern | StateStore | RecommendationStore |
|---------|------------|---------------------|
| Purpose | Catalog / sessions / audit | Recommendation rows + status |
| Table / container | `edim_agents`, … | `edim_recommendations` / `recommendations` |
| Env selector | `EDIM_STATE_STORE` | `EDIM_RECOMMENDATION_STORE` (default **inherits** StateStore) |
| `/health` key | `state_store` | `recommendation_store` |

---

## 2. Design patterns (GoF)

| Pattern | Where | Why |
|---------|-------|-----|
| **Strategy** | `RecommendationStore` protocol | Swap backends without changing API routes |
| **Factory Method** | `create_recommendation_store` / `configure_recommendation_store_from_env` | Env → concrete class |
| **Registry / Singleton** | `get_recommendation_store()` | One installed backend per process |
| **Template Method** | `RecommendationStatusMixin.update_status` | Shared get → validate → save lifecycle |
| **Null Object** | `NoneRecommendationStore` | Explicit off without `if store is None` |

Connection DSN / Cosmos / Redis resolution is shared with StateStore via `edim_dde_ai.store.connection_env` so both planes stay aligned.

---

## 3. Quick start

```python
from edim_dde_ai import configure_recommendation_store_from_env
from edim_dde_ai.recommendations import get_recommendation_store

configure_recommendation_store_from_env()  # inherits EDIM_STATE_STORE when unset
print(get_recommendation_store().name)
```

Custom backend: implement `RecommendationStore` and call `set_recommendation_store(...)`.

---

## 4. Backends

| Backend | `EDIM_RECOMMENDATION_STORE` | Typical use |
|---------|----------------------------|-------------|
| **none** | `none` | Disable persist (HTTP still works; no history ids) |
| **memory** | `memory` | Tests / ephemeral local |
| **postgres** | `postgres` | Local Compose / SDBX (recommended default with StateStore) |
| **cosmos** | `cosmos` | Deployed Apps / PROD (same account as StateStore) |
| **redis** | `redis` | Optional / cache-oriented |
| **auto** | unset / `auto` / `inherit` | Follow `EDIM_STATE_STORE` |

```bash
# Local Compose — both planes on Postgres (inherit is enough)
export EDIM_STATE_STORE=postgres
export EDIM_DATABASE_URL=postgresql://edim:edim@localhost:5432/edim
# EDIM_RECOMMENDATION_STORE unset → postgres

# Explicitly disable history while keeping catalog on Postgres
export EDIM_RECOMMENDATION_STORE=none

# Deployed
export EDIM_STATE_STORE=cosmos
export EDIM_RECOMMENDATION_STORE=cosmos   # or inherit
export EDIM_COSMOS_RECOMMENDATIONS_CONTAINER=recommendations  # optional
```

Extras: `pip install 'edim-dde-ai[postgres]'` / `[cosmos]` / `[redis]` (same as StateStore).

---

## 5. HTTP surface

On successful `POST /api/v1/cluster_tuning/recommend`, the API **best-effort** saves a `proposed` row and returns:

| Field | Meaning |
|-------|---------|
| `recommendation_id` | History id (absent if store is `none` or persist failed) |
| `recommendation_status` | e.g. `proposed` |

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/cluster_tuning/recommendations` | List (filters: `job_id`, `cluster_id`, `status`, `limit`) |
| GET | `/api/v1/cluster_tuning/recommendations/{id}` | Fetch one |
| PATCH | `/api/v1/cluster_tuning/recommendations/{id}` | Body `{ "status": "accepted" }` |

Persist failures are logged once and **do not** fail the recommend HTTP 200.

---

## 6. Protocol surface

| Method | Behavior |
|--------|----------|
| `name` | Stable id → `/health.recommendation_store` |
| `ping()` | Reachability (`none` / `memory` always True) |
| `save(record)` | Upsert by `recommendation_id` |
| `get(id)` | Fetch or `None` |
| `list(...)` | Newest-first, optional filters |
| `update_status(id, status)` | Lifecycle transition |

Document model: `RecommendationRecord` (`edim_dde_ai.recommendations.models`).

---

## 7. What this store is *not*

- Not UC job-cluster metrics (those stay in Databricks SQL)  
- Not LangSmith traces (decision detail lives in traces + request/response payloads)  
- Not agent YAML / catalog (that is StateStore + Git)  
- Not a vector index (see [Retrieval & RAG](retrieval-and-rag.md))

---

## 8. Package map

| Package | Role |
|---------|------|
| **`edim-dde-ai`** (`recommendations/`) | Protocol, models, memory/postgres/cosmos/redis/none, registry |
| **`edim-dde-ai`** (`store/connection_env.py`) | Shared Postgres/Cosmos/Redis env resolution |
| **`edim-dde-api`** | Lifespan configure; persist on recommend; list/get/patch routes |

Also: [State store](state-store.md) · [HTTP endpoints](../api/endpoints.md) · [Env vars](../reference/env-vars.md)

<!-- edim-learning-nav -->
---

← [State store](state-store.md) · [Guide home](../README.md) · [Retrieval & RAG](retrieval-and-rag.md) →
