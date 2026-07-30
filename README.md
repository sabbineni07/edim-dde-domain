# EDIM DDE Domain

**Domain package** for EDIM agents: named **sources**, generic **SQL collect**
nodes, YAML agents, and Azure AI Foundry LLM on [`edim-dde-ai`](../edim-dde-ai).

```text
API → bootstrap_agents() + set_llm_provider(Foundry)
         │
    sources.yaml  → host/path (${ENV} or concrete)
         │
    domain.sql.query  → bind :params → execute → state[output_key]
         │
    assemble / analyze / llm_chain nodes
```

See [docs/DESIGN_SOURCES_AND_SQL_NODES.md](docs/DESIGN_SOURCES_AND_SQL_NODES.md).

## Layout

```text
config/sources.yaml
src/edim_dde_domain/
  sources/           # load + resolve + auth (Apps OAuth | az login)
  nodes/sql_query.py # domain.sql.query
  tools/sql.py
  llm/               # Foundry provider + JSON helpers
  agents/...         # YAML + logic + content/prompts|skills
  bootstrap.py
```

## Configure

```bash
DATABRICKS_HOST=adb-….azuredatabricks.net
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<id>
DATABRICKS_JOB_CLUSTER_METRICS_TABLE=catalog.schema.job_cluster_metrics
DATABRICKS_SPARK_METRICS_TABLE=catalog.schema.spark_metrics
DATABRICKS_SPARK_LOGS_TABLE=catalog.schema.spark_logs

AZURE_OPENAI_ENDPOINT=https://….openai.azure.com
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
# Local Foundry auth: az login
# Prod SP (inject from Key Vault into env):
# AZURE_TENANT_ID=…
# AZURE_CLIENT_ID=…
# AZURE_CLIENT_SECRET=…
```

### Auth

| Target | Local | Databricks Apps / prod |
|--------|-------|------------------------|
| **SQL warehouse** | `az login` | `X-Forwarded-Access-Token` → API middleware |
| **Foundry LLM** | `az login` | `AZURE_TENANT_ID` + `AZURE_CLIENT_ID` + `AZURE_CLIENT_SECRET` (from Key Vault → env) |

No offline SQL stubs in production code — tests inject `metrics` / `evidence_pack` overrides and a fake LLM (`tests/llm_stub.py`).

## Setup / test

```bash
cd /Users/sabbineni/projects/edim/edim-dde-domain
pip install -r requirements.txt && pip install -e ".[dev]"
pytest -q
```
