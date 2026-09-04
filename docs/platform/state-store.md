# Control-plane state store (Postgres · Cosmos · Redis · memory)

**Learning path:** C6 · [Preface](../README.md)  
**← Previous:** [LangSmith setup](langsmith-setup.md) · **Next:** [Recommendation store](recommendation-store.md) →

## Chapter summary

What the **control-plane state store** is, why it is pluggable (memory / Postgres / Cosmos / Redis), and how it relates to `*.agent.yaml` in source control. Catalog metadata and sessions live here — not vector indexes.

**Outcome:** you pick a backend for local vs deployed without mixing knowledge-plane concerns.

---

This guide explains **what the control plane is**, **why EDIM has a pluggable state store**, how **Postgres (local)** and **Cosmos DB (deployed)** fit, and how this relates to **`*.agent.yaml` in Azure DevOps**.

---

## 1. Control plane vs data plane (detailed)

EDIM is split into planes so concerns stay clean:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ CONTROL PLANE  — “manage & remember the system”                         │
│  • Agent catalog metadata (owner, risk tier, lifecycle)                 │
│  • Sessions / HITL state                                                │
│  • Audit events (who registered / promoted what)                        │
│  Backed by: StateStore → memory | postgres | cosmos | redis             │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│ DATA PLANE  — “do the work of one request”                               │
│  • LangGraph execution from *.agent.yaml                                │
│  • Databricks SQL / Unity Catalog telemetry                             │
│  • Azure AI Foundry LLM calls                                           │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│ OBSERVABILITY PLANE  — “watch runs”                                     │
│  • LangSmith (default) or MLflow via ObservabilityProvider              │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│ SOURCE CONTROL  — “author & review definitions”                         │
│  • Azure DevOps / Git: *.agent.yaml, prompts, Python nodes, CI          │
└─────────────────────────────────────────────────────────────────────────┘
```

### What “control plane” means in practice

| Concept | Meaning |
|---------|---------|
| **Control plane** | APIs and storage that **configure, catalog, and govern** agents — not the SQL/LLM computation itself |
| **App data** | Operational JSON documents: registry rows, session blobs, audit events |
| **Not control plane** | Job metrics in UC, Foundry completions, LangSmith traces, the YAML graph definition file |

**Analogy:** In Kubernetes, etcd + API server are control plane; your pods doing work are data plane. In EDIM, Postgres/Cosmos are closer to etcd for *agent platform metadata*; Databricks+Foundry are the workers.

### What goes into `EDIM_STATE_STORE` (with examples)

Selected by **`EDIM_STATE_STORE`** (`memory` | `postgres` | `cosmos` | `redis`).  
This store does **not** hold SQL metrics, Foundry completions, or recommendation history.

| Document | When written | Example fields |
|----------|--------------|----------------|
| **Agent catalog** (`AgentRecord`) | API lifespan: `sync_registered_agents_to_store` after YAML bootstrap | `agent_id`, `display_name`, `version`, `owner`, `risk_tier`, `lifecycle`, `hitl_required`, `source_path`, `git_sha` |
| **Sessions** (`SessionRecord`) | `hitl.gate` pause and `/api/v1/sessions` start/resume | `session_id`, `agent_id`, `status` (`waiting_hitl` / `closed`), state blob, `request_id` |
| **Audit** (`AuditEvent`) | Register / sync / HITL pause-resume-close | `event_id`, `actor`, `action`, `agent_id`, `detail` |

Example **agent catalog** row (Cosmos `agents` / Postgres `edim_agents` payload):

```json
{
  "agent_id": "cluster_tuning",
  "display_name": "DBX Cluster Tuning",
  "version": 1,
  "owner": "platform-team",
  "risk_tier": "medium",
  "lifecycle": "approved",
  "hitl_required": false,
  "source_path": ".../cluster_tuning.agent.yaml",
  "git_sha": "abc1234",
  "updated_at": "2026-08-16T12:00:00+00:00"
}
```

Example **audit** event:

```json
{
  "event_id": "…",
  "actor": "api-lifespan",
  "action": "agent_synced",
  "agent_id": "spark_rca",
  "detail": {"version": 1},
  "created_at": "2026-08-16T12:00:00+00:00"
}
```

**Not in StateStore:** HTTP recommendation bodies, job sizing outcomes, RCA analyses — those go to **`EDIM_RECOMMENDATION_STORE`** ([Recommendation store](recommendation-store.md)).

**Session checkpoints are separate:** `EDIM_CHECKPOINTER` persists LangGraph
execution state and in-thread messages for agents with a `memory` + `session`
YAML policy. It is not a replacement for StateStore HITL sessions or
RecommendationStore product history. Local Compose / `host-run` default to
``postgres`` (same ``EDIM_DATABASE_URL``) so follow-ups survive API restarts.

```bash
# Choose the control-plane backend
export EDIM_STATE_STORE=postgres   # local Compose
# export EDIM_STATE_STORE=cosmos   # deployed Apps / PROD
```

---

## 1b. Design patterns (GoF)

| Pattern | Where | Example |
|---------|-------|---------|
| **Strategy** | `StateStore` backends | `EDIM_STATE_STORE=postgres` vs `cosmos` |
| **Protocol** | `store/protocols.py` | Agent/session/audit CRUD |
| **Registry** | process-wide `get_state_store()` | Lifespan installs one backend |
| **Facade** | `configure_state_store_from_env`, `sync_registered_agents_to_store` | API does not talk SQL/Cosmos SDK |
| **DTO / Record** | `AgentRecord`, `SessionRecord`, `AuditEvent` | Backend-agnostic documents |

```python
from edim_dde_ai import configure_state_store_from_env, sync_registered_agents_to_store
from edim_dde_ai.store import get_state_store

configure_state_store_from_env()
sync_registered_agents_to_store(actor="api-lifespan")
print(get_state_store().list_agents())
```

---

## 2. Does this change Azure DevOps `*.agent.yaml`?

**No — Git remains the source of truth for agent graphs.**

| Artifact | Where it lives | Changes with StateStore? |
|----------|----------------|---------------------------|
| `*.agent.yaml` graph, nodes, edges | **Azure DevOps / Git** | **Unchanged** — still PR-reviewed, CI-validated |
| Prompts / skills under `content/` | **Git** (with the agent package) | Unchanged by default |
| Owner, risk_tier, lifecycle, git_sha pointer | **State store** (Postgres/Cosmos/…) | **New** catalog fields |
| Session / HITL resume state | **State store** | New when you use sessions |

### Recommended lifecycle (DevOps + store)

```text
1. Engineer edits spark_rca.agent.yaml in Azure DevOps → PR → CI (schema + tests)
2. Deploy / API start → bootstrap_agents() loads YAML into in-process LangGraph registry
3. sync_registered_agents_to_store() upserts AgentRecord into Postgres or Cosmos
4. Operators query the catalog (lifecycle=approved, owner=…) without parsing Git
5. Runtime still executes the graph compiled from YAML — store does not replace YAML
```

You *may* later store a YAML snapshot in Cosmos for audit, but **authoring stays in DevOps**.

---

## 3. Plug-and-play backends

Same pattern as observability:

| Backend | `EDIM_STATE_STORE` | Typical use |
|---------|-------------------|-------------|
| **memory** | `memory` (default) | Tests / single-process demos — lost on restart |
| **postgres** | `postgres` | **Local, SDBX, DEV** — Docker Compose |
| **cosmos** | `cosmos` | **Deployed** Apps / UAT / PROD |
| **redis** | `redis` | Sessions/cache; not ideal alone as catalog SoR |

```bash
# Local development
EDIM_STATE_STORE=postgres
EDIM_DATABASE_URL=postgresql://edim:edim@localhost:5432/edim

# Deployed
EDIM_STATE_STORE=cosmos
EDIM_COSMOS_ENDPOINT=https://….documents.azure.com:443/
EDIM_COSMOS_KEY=…          # from Key Vault
EDIM_COSMOS_DATABASE=edim
```

Install extras:

```bash
pip install 'edim-dde-ai[postgres]'   # local
pip install 'edim-dde-ai[cosmos]'     # deployed
pip install 'edim-dde-ai[redis]'      # optional sessions
```

---

## 4. Where the code lives

| Package | Responsibility |
|---------|----------------|
| **`edim-dde-ai`** (`store/`) | `StateStore` protocol, models, memory/postgres/cosmos/redis, sync helper |
| **`edim-dde-api`** | `configure_state_store_from_env()` + `sync_registered_agents_to_store()` on lifespan |
| **`edim-dde-domain`** | Unchanged agent YAML; optional `metadata:` block in YAML feeds the catalog |

`/health` reports the active store:

```json
{
  "status": "ok",
  "agents": ["cluster_tuning", "spark_rca"],
  "version": "1.0.0",
  "observability": "langsmith",
  "state_store": "postgres"
}
```

---

## 5. Data model

### AgentRecord (catalog — not the graph)

| Field | Purpose |
|-------|---------|
| `agent_id` | Matches YAML `agent_id` |
| `display_name`, `version` | From definition |
| `owner`, `risk_tier`, `lifecycle`, `hitl_required` | From YAML `metadata:` (optional) |
| `source_path` | Path when loaded from disk |
| `git_sha` | From `EDIM_GIT_SHA` / `BUILD_SOURCEVERSION` when set in CI |
| `extra` | Other metadata keys |
| `updated_at` | ISO timestamp |

Example YAML metadata (still in DevOps):

```yaml
agent_id: spark_rca
metadata:
  owner: platform-team
  risk_tier: medium
  lifecycle: approved
  hitl_required: false
graph:
  nodes: [...]
```

### SessionRecord

For multi-turn / future HITL: `session_id`, `agent_id`, `status`, `state` bag, `request_id`.

### AuditEvent

Append-only: `event_id`, `action` (e.g. `agent.upsert`), `actor`, `detail`.

---

## 6. Local Postgres quickstart

Postgres backs the **control-plane StateStore** (catalog / sessions) — not Databricks SQL.

**Option A — API + Postgres together (Compose + E2E):**

```bash
cd edim-dde-api
make e2e-local    # compose-up (api+postgres) + dry smoke
# or: make compose-up && make e2e-dry && make compose-down
```

See `edim-dde-api/docker-compose.yml` (sibling package) and [Deploy & hosting §6.1](../api/deploy-and-hosting.md#61-docker-compose-api-postgres-recommended-locally).

**Option B — Postgres only (API via host uvicorn)** — use when `az login` must stay on the laptop (Docker proxy/kernel limits):

```bash
cd edim-dde-api
az login
# Foundry/Databricks vars in ../edim-dde-domain/.env
make host-run          # starts Postgres in Docker + uvicorn on the host
# API: http://127.0.0.1:8080/health
# Ctrl+C stops uvicorn; Postgres keeps running → make pg-down
```

Or split the steps:

```bash
make pg-up             # Docker Postgres only
make host-run          # (pg-up is implied) uvicorn with EDIM_STATE_STORE=postgres → localhost:5432
```

Manual equivalent (workspace root):

```bash
docker compose -f docker-compose.state-store.yml up -d
pip install 'edim-dde-ai[postgres]'
export EDIM_STATE_STORE=postgres
export EDIM_DATABASE_URL=postgresql://edim:edim@localhost:5432/edim
export EDIM_ENV=sdbx
uvicorn edim_dde_api.main:app --port 8080
curl -s localhost:8080/health
```

On startup the API:

1. Configures the store  
2. Bootstraps agents from Git-packaged YAML  
3. Syncs each registered agent into Postgres (`edim_agents` + `edim_audit` tables; schema auto-created)

Optional Redis profile (postgres-only compose):

```bash
docker compose -f docker-compose.state-store.yml --profile redis up -d
export EDIM_STATE_STORE=redis
export EDIM_REDIS_URL=redis://localhost:6379/0
```

---

## 7. Deployed Cosmos quickstart

1. Create a Cosmos DB account (SQL API) in Azure.  
2. Create database `edim` (or set `EDIM_COSMOS_DATABASE`).  
3. Store the key in Key Vault; map via `EDIM_KV_SECRET_MAP` if desired.  
4. Set:

```bash
EDIM_STATE_STORE=cosmos
EDIM_COSMOS_ENDPOINT=https://<account>.documents.azure.com:443/
EDIM_COSMOS_KEY=<secret>
EDIM_COSMOS_DATABASE=edim
# optional container names:
# EDIM_COSMOS_AGENTS_CONTAINER=agents
# EDIM_COSMOS_SESSIONS_CONTAINER=sessions
# EDIM_COSMOS_AUDIT_CONTAINER=audit
```

Containers are created if missing (partition keys: `/agent_id`, `/session_id`, `/event_id`).

---

## 8. Programmatic API

```python
from edim_dde_ai.store import (
    configure_state_store_from_env,
    get_state_store,
    set_state_store,
    MemoryStateStore,
    AgentRecord,
    SessionRecord,
    sync_registered_agents_to_store,
)

configure_state_store_from_env()          # or set_state_store(MemoryStateStore())
sync_registered_agents_to_store()

store = get_state_store()
print(store.list_agents())

store.upsert_session(
    SessionRecord(session_id="s-1", agent_id="cluster_tuning", state={"step": 1})
)
```

Custom backends: implement `StateStore` and call `set_state_store(...)`.

**Related:** product recommendation history is a **separate** pluggable store (`RecommendationStore`) that reuses the same connection env helpers — see [recommendation-store.md](recommendation-store.md).

---

## 9. What StateStore is *not*

- Not a replacement for **Unity Catalog** telemetry tables  
- Not a replacement for **LangSmith** traces  
- Not where you edit agent graphs day-to-day (use **Azure DevOps**)  
- Redis alone is a weak long-term catalog — use Postgres/Cosmos for SoR  

---

## 10. Environment variable reference

| Variable | Purpose |
|----------|---------|
| `EDIM_STATE_STORE` | `memory` \| `postgres` \| `cosmos` \| `redis` |
| `EDIM_DATABASE_URL` / `DATABASE_URL` | Postgres DSN |
| `EDIM_COSMOS_ENDPOINT` | Cosmos account URI |
| `EDIM_COSMOS_KEY` | Cosmos key (Key Vault in PROD) |
| `EDIM_COSMOS_DATABASE` | Database id (default `edim`) |
| `EDIM_COSMOS_*_CONTAINER` | agents / sessions / audit container names |
| `EDIM_REDIS_URL` | Redis URL |
| `EDIM_REDIS_PREFIX` | Key prefix (default `edim`) |
| `EDIM_GIT_SHA` | Optional git SHA stamped on AgentRecord at sync |

Also listed in [Environment variables](../reference/env-vars.md).

---

## 11. Protocol surface (engineer reference)

Every backend implements:

| Method | Behavior |
|--------|----------|
| `name` | Stable id returned by `/health` → `state_store` |
| `ping()` | Reachability check |
| `upsert_agent` / `get_agent` / `list_agents` / `delete_agent` | Catalog CRUD |
| `upsert_session` / `get_session` / `delete_session` | Session docs (HITL / multi-turn later) |
| `append_audit` / `list_audit` | Append-only audit trail |

### Postgres tables (auto-created)

| Table | Key | Payload |
|-------|-----|---------|
| `edim_agents` | `agent_id` | JSONB `AgentRecord` |
| `edim_sessions` | `session_id` | JSONB `SessionRecord` |
| `edim_audit` | `event_id` | JSONB `AuditEvent` (+ index on `agent_id`) |

### API lifespan sequence

```text
Key Vault bootstrap (optional)
  → configure_observability_from_env()
  → configure_state_store_from_env()     # memory|postgres|cosmos|redis
  → configure_retrieval_from_env()       # none|faiss|azure_ai_search|…
  → bootstrap_agents()                  # load *.agent.yaml from packages / EDIM_AGENT_DIRS
  → sync_registered_agents_to_store()   # upsert AgentRecord + audit agent.upsert
  → set_llm_provider(lazy Foundry)
  → ready (/health reports observability + state_store + retrieval)
```

Failures configuring the store log a warning and fall back to in-memory so `/health` still works.

### Failure / ops notes

| Situation | Behavior |
|-----------|----------|
| Missing optional dep (`psycopg`, `azure-cosmos`, `redis`) | Startup raises → logged; process continues with memory if catch path runs |
| Bad DSN / Cosmos key | Same — warn and continue with memory when using API lifespan |
| Catalog sync fails | Agents still run from in-process registry; catalog is stale until next successful sync |
| Multi-replica API with `memory` | Each replica has its own catalog — use Postgres/Cosmos for shared control plane |

---

## Related

- [Reference architecture](../architecture/reference-architecture.md)
- [Architecture overview](../architecture/overview.md)
- [Observability providers](observability.md)
- [Security baseline](security-baseline.md)
- [Environments](environments.md)
- [Recommendation lifecycle store](recommendation-store.md)
- [Environment variables](../reference/env-vars.md)

## Summary

- StateStore holds catalog/sessions/audit; graphs stay in Git; indexes are retrieval.
- Prefer Postgres locally when testing persistence; memory for first smoke.

**Next →** [Recommendation store (C6b)](recommendation-store.md)

<!-- edim-learning-nav -->
---

← [LangSmith setup](langsmith-setup.md) · [Preface](../README.md) · [Recommendation store](recommendation-store.md) →
