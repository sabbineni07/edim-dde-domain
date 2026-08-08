# EDIM DDE Domain

**Domain package** for EDIM agents: named **sources**, generic **SQL collect**
nodes, YAML agents, and Azure AI Foundry LLM on [`edim-dde-ai`](../edim-dde-ai).

> **Temporary stack docs home:** Until a parent `edim` repo exists, the engineer guide for the whole stack (ai + domain + api) lives here: **[docs/README.md](docs/README.md)**. Sibling packages: [`edim-dde-ai`](../edim-dde-ai/), [`edim-dde-api`](../edim-dde-api/). Handoff: [`BACKLOG.md`](../BACKLOG.md).

```text
API → bootstrap_agents() + set_llm_provider(Foundry)
         │
    sources.yaml  → host/path (${ENV} or concrete)
         │
    domain.sql.query  → bind :params → execute → state[output_key]
         │
    assemble / analyze / llm_chain nodes
```

**Docs:** [Engineer guide](docs/README.md) · [Sources and SQL](docs/domain/sources-and-sql.md) · [Bundled agents](docs/domain/bundled-agents.md) · [Deep dive](docs/DESIGN_SOURCES_AND_SQL_NODES.md)

## Layout

```text
config/sources.yaml
src/edim_dde_domain/
  sources/           # load + resolve + auth (Apps OAuth | az login)
  nodes/sql_query.py # domain.sql.query
  tools/sql.py
  llm/               # Foundry provider + JSON helpers
  agents/...         # YAML + nodes + logic + optional helpers/ + content/
  bootstrap.py
```

Agent package shape: `*.agent.yaml`, `nodes.py`, `logic.py`, optional `helpers/` (rules/data), optional `content/`.

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
# EDIM_FOUNDRY_TENANT_ID=…
# EDIM_FOUNDRY_CLIENT_ID=…
# EDIM_FOUNDRY_CLIENT_SECRET=…
```

### Auth

| Target | Local | Databricks Apps / prod |
|--------|-------|------------------------|
| **SQL warehouse** | `az login` | `X-Forwarded-Access-Token` → API middleware |
| **Foundry LLM** | `az login` | `EDIM_FOUNDRY_*` (from Key Vault → env) |

No offline SQL stubs in production code — tests inject `metrics` / `evidence_pack` overrides and a fake LLM (`edim_dde_domain.testing.DomainStubLLM`).

## External agents (plugins)

Bundled agents ship inside this wheel. Additional agents can live **outside** the package:

```bash
# Comma- or os.pathsep-separated roots (each may contain nested */*.agent.yaml + nodes.py)
export EDIM_AGENT_DIRS=/opt/edim-agents/acme,/opt/edim-agents/partner
```

`bootstrap_agents()` loads those dirs automatically. Or call explicitly:

```python
from edim_dde_domain import bootstrap_agents, load_external_agents

bootstrap_agents(load_external=False)  # platform + bundled only
load_external_agents(["/opt/edim-agents/acme"])  # dirs and/or entry points
```

**Packaging entry points** (installable plugin wheels):

```toml
# in the plugin package's pyproject.toml
[project.entry-points."edim_dde.agents"]
acme = "acme_edim_agents:register"
```

```python
# acme_edim_agents/__init__.py
from pathlib import Path
from edim_dde_ai import register_from_directory

def register() -> None:
    import acme_edim_agents.nodes  # noqa: F401  — @register_node
    register_from_directory(Path(__file__).parent, recursive=True, overwrite=True)
```

## Setup / test

```bash
cd /Users/sabbineni/projects/edim/edim-dde-domain
pip install -r requirements.txt && pip install -e ".[dev]"
pytest -q
```
