# Configuration

See also [environment variables](../reference/env-vars.md).

## Minimum local (live SQL + Foundry)

```bash
az login

export DATABRICKS_HOST=adb-….azuredatabricks.net
export DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<id>
export DATABRICKS_JOB_CLUSTER_METRICS_TABLE=catalog.schema.job_cluster_metrics
export DATABRICKS_SPARK_METRICS_TABLE=catalog.schema.spark_metrics
export DATABRICKS_SPARK_LOGS_TABLE=catalog.schema.spark_logs

export AZURE_OPENAI_ENDPOINT=https://….openai.azure.com
export AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

Template: `edim-dde-domain/.env.example`.

## API-specific

```bash
# Browser CORS allow-list (empty = no cross-origin)
export EDIM_CORS_ORIGINS=http://localhost:4200

# External agent plugin roots
export EDIM_AGENT_DIRS=/opt/edim-agents/acme
```

## Run

```bash
cd edim-dde-api
uvicorn edim_dde_api.main:app --reload --port 8080
```
