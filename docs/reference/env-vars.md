# Environment variables

**Learning path:** H1 · [Guide home](../README.md)
**← Previous:** [Deploy & hosting](../api/deploy-and-hosting.md) · **Next:** [Node type ids](node-type-ids.md) →


| Variable | Used by | Purpose |
|----------|---------|---------|
| `EDIM_ENV` | API / tracing | Environment name: `sdbx` \| `dev` \| `uat` \| `intg` \| `prod` (Phase 0 focus: sdbx/dev/prod) |
| `EDIM_OBSERVABILITY` | API lifespan / AI | Backend: `langsmith` \| `mlflow` \| `none` \| `auto` (default auto) |
| `EDIM_MLFLOW_EXPERIMENT` | MLflow provider | Experiment name (default `edim-dde`) |
| `MLFLOW_TRACKING_URI` | MLflow | Tracking server / Databricks URI when using MLflow |
| `EDIM_STATE_STORE` | API lifespan / AI | Control plane: `memory` \| `postgres` \| `cosmos` \| `redis` (default `memory`) |
| `EDIM_DATABASE_URL` | Postgres store | e.g. `postgresql://edim:edim@localhost:5432/edim` |
| `EDIM_COSMOS_ENDPOINT` | Cosmos store | Cosmos account URI |
| `EDIM_COSMOS_KEY` | Cosmos store | Account key (prefer Key Vault in PROD) |
| `EDIM_COSMOS_DATABASE` | Cosmos store | Database id (default `edim`) |
| `EDIM_COSMOS_AGENTS_CONTAINER` | Cosmos store | Container id (default `agents`) |
| `EDIM_COSMOS_SESSIONS_CONTAINER` | Cosmos store | Container id (default `sessions`) |
| `EDIM_COSMOS_AUDIT_CONTAINER` | Cosmos store | Container id (default `audit`) |
| `EDIM_REDIS_URL` | Redis store | e.g. `redis://localhost:6379/0` |
| `EDIM_GIT_SHA` | Catalog sync | Optional git SHA stamped on agent records |
| `EDIM_RETRIEVAL` | API lifespan / AI | Retrieval: `none` \| `memory` \| `faiss` \| `azure_ai_search` \| `databricks_vector` |
| `EDIM_FAISS_INDEX_PATH` | FAISS provider | Local dir or Databricks Volume for `{corpus}.faiss` |
| `EDIM_FAISS_DIM` | FAISS provider | Hash embedding dim (default 384) |
| `EDIM_AZURE_SEARCH_ENDPOINT` | Azure AI Search | Service endpoint |
| `EDIM_AZURE_SEARCH_KEY` | Azure AI Search | Key (Key Vault in PROD) |
| `EDIM_AZURE_SEARCH_INDEX` | Azure AI Search | Default index name |
| `EDIM_AZURE_SEARCH_CORPUS_MAP` | Azure AI Search | Optional `corpus:index,...` |
| `EDIM_DBX_VS_ENDPOINT` | Databricks VS | Vector Search endpoint name |
| `EDIM_DBX_VS_INDEX` | Databricks VS | Default index name |
| `EDIM_DBX_VS_CORPUS_MAP` | Databricks VS | Optional `corpus:index,...` |
| `DATABRICKS_HOST` | domain sources | SQL warehouse hostname |
| `DATABRICKS_HTTP_PATH` | domain sources | Warehouse HTTP path |
| `DATABRICKS_JOB_CLUSTER_METRICS_TABLE` | cluster_tuning SQL | UC FQN (`catalog.schema.table`) |
| `DATABRICKS_SPARK_METRICS_TABLE` | spark_rca SQL | UC FQN |
| `DATABRICKS_SPARK_LOGS_TABLE` | spark_rca SQL | UC FQN |
| `AZURE_OPENAI_ENDPOINT` | Foundry | OpenAI v1 endpoint |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Foundry | Deployment name |
| `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` | Foundry (prod) | Foundry workload SP (often from Key Vault) |
| `AZURE_KEY_VAULT_URL` | API lifespan | Vault URI for secret bootstrap |
| `EDIM_KV_SECRET_MAP` | Key Vault | Optional `secret:ENV_VAR,...` map |
| `EDIM_KV_FORCE` | Key Vault | `1` = overwrite existing env from vault |
| `EDIM_KV_CLIENT_ID` / `EDIM_KV_CLIENT_SECRET` / `EDIM_KV_TENANT_ID` | Key Vault | Optional dedicated vault-reader SP |
| `DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET` | Apps (injected) | App SP — used to open KV when tenant set |
| `LANGCHAIN_TRACING_V2` | LangSmith | Set `true` to enable tracing |
| `LANGCHAIN_API_KEY` | LangSmith | API key (from UI or Key Vault) |
| `LANGCHAIN_PROJECT` | LangSmith | Project name (`edim-dde-sdbx` / `edim-dde-dev` / `edim-dde-prod`) |
| `LANGCHAIN_ENDPOINT` | LangSmith | Default `https://api.smith.langchain.com` |
| `EDIM_LANGSMITH_ENABLED` | runtime | Set `false` to force-disable EDIM tracing helpers |
| `EDIM_STRICT_STARTUP` | API | `1`/`true` → fail process start if Foundry endpoint missing |
| `EDIM_REQUIRE_SQL` | API | With strict: also require Databricks host/path |

Table FQNs must match identifier validation (letters/digits/underscore; `schema.table` or `catalog.schema.table`).

See also: [retrieval & RAG](../platform/retrieval-and-rag.md), [state store](../platform/state-store.md), [observability providers](../platform/observability.md), [environments](../platform/environments.md), [LangSmith setup](../platform/langsmith-setup.md), [security baseline](../platform/security-baseline.md), [access & permissions](../platform/access-and-permissions.md), [deploy & hosting](../api/deploy-and-hosting.md).

<!-- edim-learning-nav -->
---

← [Deploy & hosting](../api/deploy-and-hosting.md) · [Guide home](../README.md) · [Node type ids](node-type-ids.md) →
