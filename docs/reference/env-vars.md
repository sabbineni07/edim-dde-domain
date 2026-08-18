# Environment variables

**Learning path:** H1 · [Guide home](../README.md)
**← Previous:** [Deploy & hosting](../api/deploy-and-hosting.md) · **Next:** [Node type ids](node-type-ids.md) →


| Variable | Used by | Purpose |
|----------|---------|---------|
| `EDIM_ENV` | API / tracing / workspace resolver | Environment name: `sdbx` \| `dev` \| `uat` \| `intg` \| `prod` (Current focus: sdbx/dev/prod). **Binds the process** — workspace catalog only registers entries with matching `env`. |
| `EDIM_DEFAULT_WORKSPACE_ID` | workspace resolver | Default within-env workspace when the request omits `workspace_id` (required if `workspaces.yaml` has multiple entries for this env) |
| `EDIM_OBSERVABILITY` | API lifespan / AI | Backend: `langsmith` \| `mlflow` \| `none` \| `auto` (default auto) |
| `EDIM_MLFLOW_EXPERIMENT` | MLflow provider | Experiment name (default `edim-dde`) |
| `MLFLOW_TRACKING_URI` | MLflow | Tracking server / Databricks URI when using MLflow |
| `EDIM_STATE_STORE` | API lifespan / AI | **Control plane** backend: `memory` \| `postgres` \| `cosmos` \| `redis` (default `memory`). Holds agent catalog, sessions, audit — see [§ State vs recommendation stores](#state-store-vs-recommendation-store) |
| `EDIM_RECOMMENDATION_STORE` | API lifespan / AI | **Product history** backend: `none` \| `memory` \| `postgres` \| `cosmos` \| `redis` \| `auto` (default **inherits** `EDIM_STATE_STORE`). Holds tuning/RCA recommendation rows + status |
| `EDIM_DATABASE_URL` | Postgres store | e.g. `postgresql://edim:edim@localhost:5432/edim` (StateStore + RecommendationStore) |
| `EDIM_COSMOS_ENDPOINT` | Cosmos store | Cosmos account URI |
| `EDIM_COSMOS_KEY` | Cosmos store | Account key (prefer Key Vault in PROD) |
| `EDIM_COSMOS_DATABASE` | Cosmos store | Database id (default `edim`) |
| `EDIM_COSMOS_AGENTS_CONTAINER` | Cosmos store | Container id (default `agents`) |
| `EDIM_COSMOS_SESSIONS_CONTAINER` | Cosmos store | Container id (default `sessions`) |
| `EDIM_COSMOS_AUDIT_CONTAINER` | Cosmos store | Container id (default `audit`) |
| `EDIM_COSMOS_RECOMMENDATIONS_CONTAINER` | Cosmos recommendation store | Container id (default `recommendations`) |
| `EDIM_REDIS_URL` | Redis store | e.g. `redis://localhost:6379/0` |
| `EDIM_GIT_SHA` | Catalog sync | Optional git SHA stamped on agent records |
| `EDIM_RETRIEVAL` | API lifespan / AI | Retrieval: `none` \| `memory` \| `faiss` \| `azure_ai_search` \| `databricks_vector` |
| `EDIM_FAISS_INDEX_PATH` | FAISS provider | Local dir or Databricks Volume for `{corpus}.faiss` |
| `EDIM_FAISS_DIM` | FAISS provider | Hash embedding dim (default 384) |
| `EDIM_AZURE_SEARCH_ENDPOINT` | Azure AI Search | Service endpoint |
| `EDIM_AZURE_SEARCH_KEY` | Azure AI Search | Key (Key Vault in PROD) |
| `EDIM_AZURE_SEARCH_INDEX` | Azure AI Search | Default index name |
| `EDIM_AZURE_SEARCH_CORPUS_MAP` | Azure AI Search | Optional `corpus:index,...` |

Hands-on Azure service + indexes + ingest: [Retrieval & RAG §8](../platform/retrieval-and-rag.md#8-setting-up-azure-ai-search-for-a-real-retrievalprovider).

| `EDIM_DBX_VS_ENDPOINT` | Databricks VS | Vector Search endpoint name |
| `EDIM_DBX_VS_INDEX` | Databricks VS | Default index name |
| `EDIM_DBX_VS_CORPUS_MAP` | Databricks VS | Optional `corpus:index,...` |
| `EDIM_WEB_SEARCH` | API lifespan / AI | Optional public-web provider: `none` (default) or `http_json`; RCA YAML must also enable its web nodes |
| `EDIM_WEB_SEARCH_ENDPOINT` | HTTP JSON web provider | HTTPS search endpoint accepting `q` and `count` query parameters |
| `EDIM_WEB_SEARCH_API_KEY` | HTTP JSON web provider | Provider API key (prefer Key Vault) |
| `EDIM_WEB_SEARCH_KEY_HEADER` | HTTP JSON web provider | API-key header (default `Ocp-Apim-Subscription-Key`) |
| `EDIM_WEB_SEARCH_TIMEOUT_SECONDS` | HTTP JSON web provider | Bounded request timeout (default 8 seconds) |
| `DATABRICKS_HOST` | domain sources / workspace fallback | SQL warehouse hostname (process default; catalog may override per workspace) |
| `DATABRICKS_HTTP_PATH` | domain sources / workspace fallback | Warehouse HTTP path |
| `DATABRICKS_JOB_CLUSTER_METRICS_TABLE` | cluster_tuning SQL / workspace fallback | UC FQN (`catalog.schema.table`) |
| `DATABRICKS_SPARK_METRICS_TABLE` | spark_rca SQL / workspace fallback | UC FQN |
| `DATABRICKS_SPARK_LOGS_TABLE` | spark_rca SQL / workspace fallback | UC FQN |
| `AZURE_OPENAI_ENDPOINT` | Foundry | OpenAI v1 endpoint |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Foundry | Deployment name |
| `EDIM_FOUNDRY_TENANT_ID` / `EDIM_FOUNDRY_CLIENT_ID` / `EDIM_FOUNDRY_CLIENT_SECRET` | Foundry (prod) | Foundry workload SP (often from Key Vault). Keeps SQL `DefaultAzureCredential` clean |
| `EDIM_FOUNDRY_API_KEY` / `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_ENDPOINT_KEY` | Foundry (optional) | API key auth when SP unset (checked before `az login`) |
| `AZURE_TENANT_ID` | Apps → Key Vault | Directory GUID for Apps SP client-credentials. Not the Foundry SP |
| `AZURE_KEY_VAULT_URL` | API lifespan | Vault URI for secret bootstrap |
| `EDIM_KV_SECRET_MAP` | Key Vault | Optional `ENV_VAR:vaultSecret,...` map — [Key Vault bootstrap](../platform/key-vault-bootstrap.md) |
| `EDIM_KV_FORCE` | Key Vault | `1` = overwrite existing env from vault |
| `EDIM_KV_CLIENT_ID` / `EDIM_KV_CLIENT_SECRET` / `EDIM_KV_TENANT_ID` | Key Vault | Optional dedicated vault-reader SP |
| `DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET` | Apps (injected) | App SP — used to open KV when tenant set |
| `LANGCHAIN_TRACING_V2` | LangSmith / LangGraph | Set `true` to enable **LangGraph → LangSmith** tracing (required for EDIM) |
| `LANGCHAIN_API_KEY` | LangSmith | API key (from UI or Key Vault secret `langchain-api-key`) |
| `LANGCHAIN_PROJECT` | LangSmith | **Tracing project** name (`edim-dde-sdbx` / `edim-dde-dev` / `edim-dde-prod`) |
| `LANGCHAIN_ENDPOINT` | LangSmith | SaaS: `https://api.smith.langchain.com`; self-hosted: your `/api/v1` URL |
| `EDIM_LANGSMITH_ENABLED` | EDIM observability | Optional **off switch only**: `false` forces EDIM to ignore tracing (do not set `auto`) |
| `EDIM_STRICT_STARTUP` | API | `1`/`true` → fail process start if Foundry endpoint missing |
| `EDIM_REQUIRE_SQL` | API | With strict: also require Databricks host/path |

### LangSmith tracing

EDIM uses **LangGraph automatic tracing** (`LANGCHAIN_TRACING_V2`), not the LangSmith UI “OpenAI Agents SDK” integration. Setup and validation: [LangSmith setup guide](../platform/langsmith-setup.md).

| LangSmith UI / newer SDK docs | EDIM / LangGraph (use these) |
|-------------------------------|------------------------------|
| `LANGSMITH_TRACING=true` | **`LANGCHAIN_TRACING_V2=true`** (do not use bare `LANGCHAIN_TRACING`) |
| `LANGSMITH_API_KEY` | `LANGCHAIN_API_KEY` (aliases often work — set both if your ops standard requires `LANGSMITH_*`) |
| `LANGSMITH_PROJECT` | `LANGCHAIN_PROJECT` |
| `LANGSMITH_ENDPOINT` | `LANGCHAIN_ENDPOINT` |

The `langsmith` Python package is installed **transitively** via `langchain-core` (optional extra: `edim-dde-ai[observability]`).

Table FQNs must match identifier validation (letters/digits/underscore; `schema.table` or `catalog.schema.table`).

**Multi-workspace within one env:** see [Within-env workspace resolver](../domain/workspace-resolver.md) (`config/workspaces.yaml`). Process `DATABRICKS_*` remain the fallback when the catalog is empty for `EDIM_ENV`.

---

## State store vs recommendation store

These are **two different planes**. They often share Postgres/Cosmos connection settings, but the env vars select *what kind of data* is persisted.

```text
EDIM_STATE_STORE          →  agents / sessions / audit     (control plane)
EDIM_RECOMMENDATION_STORE →  recommend / RCA history rows  (product history)
```

| Question | `EDIM_STATE_STORE` | `EDIM_RECOMMENDATION_STORE` |
|----------|--------------------|------------------------------|
| What is it? | Platform catalog + session/audit | Durable outcomes from agent HTTP calls |
| Example contents | `{ "agent_id": "cluster_tuning", "lifecycle": "approved", … }` | `{ "recommendation_id": "…", "job_id": "123", "status": "proposed", "response": { … } }` |
| Written by | Lifespan sync / HITL sessions | `POST /api/v1/cluster_tuning/recommend`, `POST /api/v1/rca/analyze` |
| Read by | Catalog / `/health` / HITL get-resume | List/get/patch APIs, prompt historical context, experience index |
| Typical local | `postgres` | unset → inherits postgres |
| Typical deployed | `cosmos` | unset → inherits cosmos, or set `cosmos` explicitly |
| Disable? | No | `EDIM_RECOMMENDATION_STORE=none` |

```bash
# Usual: both planes on the same backend
export EDIM_STATE_STORE=cosmos
# leave EDIM_RECOMMENDATION_STORE unset → also cosmos

# History off, catalog still on
export EDIM_STATE_STORE=postgres
export EDIM_RECOMMENDATION_STORE=none
```

Guides with full examples:

- [Control-plane state store](../platform/state-store.md) — what goes into StateStore  
- [Recommendation lifecycle store](../platform/recommendation-store.md) — what goes into RecommendationStore  

---

## Key Vault–related vars

Canonical how-to (defaults, `EDIM_KV_SECRET_MAP` examples, force overwrite):

→ **[Key Vault bootstrap](../platform/key-vault-bootstrap.md)**

This page stays a **catalog** of names; do not duplicate secret-map tutorials here.

See also: [access & permissions](../platform/access-and-permissions.md), [deploy & hosting](../api/deploy-and-hosting.md), [environments](../platform/environments.md), [security baseline](../platform/security-baseline.md).

<!-- edim-learning-nav -->
---

← [Deploy & hosting](../api/deploy-and-hosting.md) · [Guide home](../README.md) · [Node type ids](node-type-ids.md) →
