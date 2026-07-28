# EDIM DDE Domain

**Domain package** for EDIM agents: named **sources**, generic **SQL collect**
nodes, and YAML agents on [`edim-dde-ai`](../edim-dde-ai).

```text
API → bootstrap_agents() → create_agent().invoke(state)
         │
    sources.yaml  → connection (host/path via ${ENV}, token from env)
         │
    domain.sql.query  → bind :params → execute → state[output_key]
         │
    assemble / analyze nodes
```

See [docs/DESIGN_SOURCES_AND_SQL_NODES.md](docs/DESIGN_SOURCES_AND_SQL_NODES.md).

## Layout

```text
config/sources.yaml                 # also shipped under src/edim_dde_domain/config/
src/edim_dde_domain/
  sources/                          # load + resolve named sources
  nodes/sql_query.py                # domain.sql.query
  tools/sql.py                      # prepare_query + execute_sql
  tools/evidence_pack.py            # RCA assemble (pure)
  agents/spark_rca|cluster_tuning/  # YAML graphs + analysis nodes
```

## Configure

```bash
DATABRICKS_HOST=adb-….azuredatabricks.net
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<id>
# Optional PAT — if unset, auth mode "auto" uses DefaultAzureCredential (az login / MI)
# DATABRICKS_TOKEN=dapi…
DATABRICKS_SPARK_LOGS_TABLE=catalog.schema.spark_logs
DATABRICKS_SPARK_METRICS_TABLE=catalog.schema.spark_metrics
DATABRICKS_JOB_CLUSTER_METRICS_TABLE=catalog.schema.job_cluster_metrics
EDIM_DOMAIN_ALLOW_STUB=true
```

### Source auth (`sources.yaml`)

`auth` is **optional**. Default mode is **`auto`**:

1. Use `DATABRICKS_TOKEN` (or `token_env`) if set  
2. Else `DefaultAzureCredential` / `az login` / Managed Identity (or `AZURE_CLIENT_*` SP)

```yaml
# omit auth entirely → auto
# or:
auth: { mode: auto }
auth: { mode: env_token, token_env: DATABRICKS_TOKEN }
auth: { mode: azure_credential }
```

## Setup / test

```bash
cd /Users/sabbineni/projects/edim/edim-dde-domain
pip install -r requirements.txt && pip install -e ".[dev]"
pytest -q
```
