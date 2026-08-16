# Recommendation lifecycle store (Postgres · Cosmos · Redis · memory · none)

**Learning path:** C6b · [Guide home](../README.md)
**← Previous:** [Control-plane state store](state-store.md) · **Next:** [Retrieval & RAG](retrieval-and-rag.md) →

---

## 1. Why a separate store?

`StateStore` is the **control plane** (agent catalog, sessions, audit).  
`RecommendationStore` is **product history** — persist cluster-tuning (and future) recommendations beyond a single HTTP response, with lifecycle status:

`proposed` → `accepted` | `rejected` | `applied` | `superseded`

Same **Strategy + Factory + Registry** pattern as StateStore / Observability / Retrieval — plug-and-play backends, one process-wide instance.

**Derived experience index:** `set_recommendation_store` wraps backends in `ExperienceIndexingStore` so each `save` / `update_status` also upserts (or deletes) a resource-feature/action card into the active `RetrievalProvider` corpus (see [Retrieval & RAG §6c](retrieval-and-rag.md#6c-experience-index-platform-all-future-agents)). The store remains the system of record; vectors are a derived view for **feature** similarity across jobs.

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

## 4b. Setting up Cosmos for `EDIM_RECOMMENDATION_STORE=cosmos`

Use this when product history should live in **Azure Cosmos DB (SQL API)** —
typically the same account as StateStore for deployed Apps / PROD. The SDK
**creates the database and `recommendations` container if missing** (partition
key `/recommendation_id`).

### Step 1 — Create (or reuse) a Cosmos DB account

Portal: **Create a resource** → **Azure Cosmos DB** → **Azure Cosmos DB for NoSQL**.

Or CLI:

```bash
az cosmosdb create \
  --name <your-edim-cosmos> \
  --resource-group <rg> \
  --locations regionName=<region> failoverPriority=0 \
  --default-consistency-level Session \
  --enable-free-tier false
```

Copy:

- **URI** → `EDIM_COSMOS_ENDPOINT` (e.g. `https://<account>.documents.azure.com:443/`)
- **Primary key** → `EDIM_COSMOS_KEY` (Key Vault in PROD)

### Step 2 — Database id

Default database id is **`edim`**. Create it in the portal, or let the first
`CosmosRecommendationStore` / `CosmosStateStore` call create it via
`create_database_if_not_exists`.

Optional: `EDIM_COSMOS_DATABASE=edim` (or another name you prefer).

### Step 3 — Recommendations container

| Setting | Value |
|---------|--------|
| Container id | `recommendations` (override with `EDIM_COSMOS_RECOMMENDATIONS_CONTAINER`) |
| Partition key | `/recommendation_id` (required by EDIM — do not use `/id` alone) |
| Throughput | Autoscale or 400 RU/s is enough for DEV |

You can create the container manually in the portal **or** leave it to the
SDK on first connect.

If StateStore also uses Cosmos, keep the same account/database and separate
containers (`agents` / `sessions` / `audit` / `recommendations`).

### Step 4 — Install the extra and wire `.env`

```bash
pip install 'edim-dde-ai[cosmos]'
# or ensure api/domain requirements include the cosmos extra
```

In `edim-dde-domain/.env` (gitignored):

```bash
# Recommendation history on Cosmos (can inherit if StateStore is also cosmos)
EDIM_RECOMMENDATION_STORE=cosmos
EDIM_COSMOS_ENDPOINT=https://<account>.documents.azure.com:443/
EDIM_COSMOS_KEY=<primary-or-secondary-key>
EDIM_COSMOS_DATABASE=edim
# EDIM_COSMOS_RECOMMENDATIONS_CONTAINER=recommendations

# Optional: also put control-plane catalog on the same account
# EDIM_STATE_STORE=cosmos
```

PROD: map the key from Key Vault, e.g.

```bash
EDIM_KV_SECRET_MAP=...,EDIM_COSMOS_KEY:cosmos-key
```

### Step 5 — Verify

```python
from edim_dde_ai.recommendations import (
    configure_recommendation_store_from_env,
    get_recommendation_store,
    RecommendationRecord,
    new_recommendation_id,
)

configure_recommendation_store_from_env()
store = get_recommendation_store()
assert store.name == "cosmos"
assert store.ping() is True

rid = new_recommendation_id()
store.save(
    RecommendationRecord(
        recommendation_id=rid,
        agent_id="cluster_tuning",
        job_id="cosmos-smoke-job",
        status="proposed",
        response={"smoke": True},
    )
)
assert store.get(rid) is not None
print("cosmos recommendation store OK", rid)
```

API health should report `"recommendation_store": "cosmos"` after restart.

### Step 6 — Backfill experiences (optional)

With `EDIM_RETRIEVAL=azure_ai_search` and Cosmos filled with real rows:

```bash
python -m edim_dde_ai.experiences.backfill --agent-id cluster_tuning --dry-run
python -m edim_dde_ai.experiences.backfill --agent-id spark_rca
```

### Common pitfalls

| Symptom | Cause / fix |
|---------|-------------|
| `RuntimeError: Cosmos backend requires EDIM_COSMOS_ENDPOINT and EDIM_COSMOS_KEY` | Env not loaded by the API process |
| `ModuleNotFoundError: azure.cosmos` | `pip install 'edim-dde-ai[cosmos]'` |
| Partition key errors on upsert | Container must use `/recommendation_id` |
| Empty CLI backfill | Store has no rows yet — run recommend/analyze first, or seed |
| Cross-partition query RU cost | Normal for `list`; tighten filters (`job_id`, `agent_id`) |

---

## 5. HTTP surface

On successful `POST /api/v1/cluster_tuning/recommend` or
`POST /api/v1/rca/analyze`, the API **best-effort** saves a `proposed` row and returns:

| Field | Meaning |
|-------|---------|
| `recommendation_id` | History id (absent if store is `none` or persist failed) |
| `recommendation_status` | e.g. `proposed` |

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/cluster_tuning/recommendations` | List (filters: `job_id`, `cluster_id`, `status`, `limit`) |
| GET | `/api/v1/cluster_tuning/recommendations/{id}` | Fetch one |
| PATCH | `/api/v1/cluster_tuning/recommendations/{id}` | Body `{ "status": "accepted" }` |
| GET | `/api/v1/rca/recommendations` | RCA list (filters: `job_id`, `status`, `limit`) |
| GET | `/api/v1/rca/recommendations/{id}` | Fetch one RCA lifecycle row |
| PATCH | `/api/v1/rca/recommendations/{id}` | Review/apply/reject an RCA diagnosis/action proposal |

Routes enforce `record.agent_id`, so an RCA id is not readable/updateable
through the tuning route (and vice versa). Persist failures are logged once and
**do not** fail the successful analysis/recommend response.

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

??? note "In depth (optional) — platform engineers — new backend + experience-index wrap"

    Read this when adding a store backend or debugging why history rows appear in
    retrieval. Day-to-day API use only needs §3–5.

    **Add a backend (Strategy + Factory).**

    1. Implement `RecommendationStore` (+ usually inherit
       `RecommendationStatusMixin` for shared lifecycle).
    2. Register it in `create_recommendation_store` /
       `configure_recommendation_store_from_env`.
    3. Reuse `edim_dde_ai.store.connection_env` for DSN/Cosmos/Redis so StateStore
       and RecommendationStore stay aligned.
    4. Document the env selector in [Env vars](../reference/env-vars.md) and the
       backend table in §4 above.
    5. Prefer **inherit from `EDIM_STATE_STORE`** unless history must diverge
       deliberately (`none` while catalog stays on Postgres is the common case).

    **Experience index is a Decorator, not a second store.**
    `set_recommendation_store` wraps every backend in `ExperienceIndexingStore`.
    On `save` / `update_status` it:

    - looks up an `ExperienceTransform` for `record.agent_id`;
    - upserts a derived feature/action card into the active `RetrievalProvider`
      (corpus from the transform); or
    - deletes the card when status is `rejected` / `superseded`.

    Failures log and never fail the HTTP recommend path. With
    `EDIM_RETRIEVAL=none` or no registered transform, wrapping is a no-op on the
    index side. The store remains the system of record; vectors are a derived
    view. Details: [Retrieval & RAG §6c](retrieval-and-rag.md#6c-experience-index-platform-all-future-agents).

    **Do not** put vector search inside RecommendationStore itself — that would
    break plug-and-play backends and mix product history with retrieval.

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
