# Environment variables

| Variable | Used by | Purpose |
|----------|---------|---------|
| `DATABRICKS_HOST` | domain sources | SQL warehouse hostname |
| `DATABRICKS_HTTP_PATH` | domain sources | Warehouse HTTP path |
| `DATABRICKS_JOB_CLUSTER_METRICS_TABLE` | cluster_tuning SQL | UC FQN (`catalog.schema.table`) |
| `DATABRICKS_SPARK_METRICS_TABLE` | spark_rca SQL | UC FQN |
| `DATABRICKS_SPARK_LOGS_TABLE` | spark_rca SQL | UC FQN |
| `AZURE_OPENAI_ENDPOINT` | Foundry | OpenAI v1 endpoint |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Foundry | Deployment name |
| `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` | Foundry (prod) | Service principal |
| `EDIM_CORS_ORIGINS` | API | Comma-separated browser origins |
| `EDIM_AGENT_DIRS` | domain bootstrap | External agent directory roots |

Table FQNs must match identifier validation (letters/digits/underscore; `schema.table` or `catalog.schema.table`).
