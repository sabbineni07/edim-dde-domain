# Environment variables

| Variable | Used by | Purpose |
|----------|---------|---------|
| `EDIM_ENV` | API / tracing | Environment name: `sdbx` \| `dev` \| `uat` \| `intg` \| `prod` (Phase 0 focus: sdbx/dev/prod) |
| `EDIM_OBSERVABILITY` | API lifespan / AI | Backend: `langsmith` \| `mlflow` \| `none` \| `auto` (default auto) |
| `EDIM_MLFLOW_EXPERIMENT` | MLflow provider | Experiment name (default `edim-dde`) |
| `MLFLOW_TRACKING_URI` | MLflow | Tracking server / Databricks URI when using MLflow |
| `DATABRICKS_HOST` | domain sources | SQL warehouse hostname |
| `DATABRICKS_HTTP_PATH` | domain sources | Warehouse HTTP path |
| `DATABRICKS_JOB_CLUSTER_METRICS_TABLE` | cluster_tuning SQL | UC FQN (`catalog.schema.table`) |
| `DATABRICKS_SPARK_METRICS_TABLE` | spark_rca SQL | UC FQN |
| `DATABRICKS_SPARK_LOGS_TABLE` | spark_rca SQL | UC FQN |
| `AZURE_OPENAI_ENDPOINT` | Foundry | OpenAI v1 endpoint |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Foundry | Deployment name |
| `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` | Foundry (prod) | Service principal (prefer Key Vault) |
| `AZURE_KEY_VAULT_URL` | API lifespan | Vault URI for secret bootstrap |
| `EDIM_KV_SECRET_MAP` | Key Vault | Optional `secret:ENV_VAR,...` map (defaults include Foundry SP + LangSmith key) |
| `LANGCHAIN_TRACING_V2` | LangSmith | Set `true` to enable tracing |
| `LANGCHAIN_API_KEY` | LangSmith | API key (from UI or Key Vault) |
| `LANGCHAIN_PROJECT` | LangSmith | Project name (`edim-dde-sdbx` / `edim-dde-dev` / `edim-dde-prod`) |
| `LANGCHAIN_ENDPOINT` | LangSmith | Default `https://api.smith.langchain.com` |
| `EDIM_LANGSMITH_ENABLED` | runtime | Set `false` to force-disable EDIM tracing helpers |
| `EDIM_CORS_ORIGINS` | API | Comma-separated browser origins |
| `EDIM_AGENT_DIRS` | domain bootstrap | External agent directory roots |

Table FQNs must match identifier validation (letters/digits/underscore; `schema.table` or `catalog.schema.table`).

See also: [observability providers](../platform/observability.md), [environments](../platform/environments.md), [LangSmith setup](../platform/langsmith-setup.md), [security baseline](../platform/security-baseline.md).
