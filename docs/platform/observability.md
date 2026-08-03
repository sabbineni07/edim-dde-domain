# Observability providers (LangSmith · MLflow · none)

EDIM supports **pluggable observability backends** in `edim-dde-ai`, selected at process start (same pattern as `set_llm_provider`).

**Default for R1:** LangSmith (when tracing env is on).  
**Also available:** MLflow (optional extra), or `none`.

---

## Where it lives

| Package | Role |
|---------|------|
| **`edim-dde-ai`** | `ObservabilityProvider` protocol, NoOp / LangSmith / MLflow adapters, registry |
| **`edim-dde-api`** | Calls `configure_observability_from_env()` on lifespan; passes `request_id` on invoke |
| **`edim-dde-domain`** | No vendor SDK — product agents stay free of tracing imports |

All agents (HTTP, CLI, plugins, `invoke_agent` children) go through `MetadataAgent.invoke`, which calls the active provider.

---

## Choosing a backend

```bash
# Explicit (recommended in shared envs)
EDIM_OBSERVABILITY=langsmith   # or mlflow | none | auto

# auto (default when unset): langsmith if LANGCHAIN_TRACING_V2=true, else none
```

| Value | Behavior |
|-------|----------|
| `langsmith` | Enrich LangGraph config for LangSmith; ensure `LANGCHAIN_TRACING_V2=true` if unset |
| `mlflow` | Set experiment + tags; optional `mlflow.langchain.autolog` · requires `pip install 'edim-dde-ai[mlflow]'` |
| `none` | Correlation tags only (`request_id`, `env`) — no external SaaS |
| `auto` | LangSmith if tracing env on, otherwise none |

`/health` reports the active backend:

```json
{"status":"ok","agents":[...],"version":"1.0.0","observability":"langsmith"}
```

---

## Programmatic selection

```python
from edim_dde_ai import set_observability_provider, configure_observability_from_env
from edim_dde_ai.observability import LangSmithObservability, NoOpObservability

# From env
configure_observability_from_env()

# Or explicit
set_observability_provider(LangSmithObservability())
# set_observability_provider(NoOpObservability())
```

Custom backends: implement `ObservabilityProvider.merge_invoke_kwargs` and call `set_observability_provider(...)`.

---

## LangSmith (recommended)

See [langsmith-setup.md](langsmith-setup.md).

```bash
EDIM_OBSERVABILITY=langsmith
EDIM_ENV=dev
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=edim-dde-dev
```

---

## MLflow (optional)

Use when your org standardizes on MLflow / Databricks experiment tracking for models and metrics. Agent-level prompt debugging is still stronger in LangSmith.

```bash
pip install 'edim-dde-ai[mlflow]'

EDIM_OBSERVABILITY=mlflow
EDIM_MLFLOW_EXPERIMENT=edim-dde
# MLFLOW_TRACKING_URI=databricks  # or http://...
```

You can run **LangSmith for traces** in one env and **MLflow in another** by changing `EDIM_OBSERVABILITY` — not both at once with the built-in registry (single active provider). A composite provider can be added later if needed.

---

## Correlation fields (all backends)

| Field | Source |
|-------|--------|
| `request_id` | `X-Request-Id` or generated UUID |
| `edim_env` | `EDIM_ENV` |
| `agent_id` | Agent definition |
| `observability` | Backend name in metadata |

---

## Related

- [LangSmith setup](langsmith-setup.md)
- [Config → observability](../architecture/config-to-observability.md)
- [Environment variables](../reference/env-vars.md)
