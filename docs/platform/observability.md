# Observability providers (C4) — LangSmith · MLflow · none

**Learning path:** C4 · [Guide home](../README.md)  
**← Previous:** [PII guardrails](pii-guardrails.md) · **Next:** [LangSmith setup](langsmith-setup.md) →

EDIM supports **pluggable observability backends** in `edim-dde-ai`, selected at process start (same Strategy pattern as `LLMProvider`, `StateStore`, `RetrievalProvider`).

**Default for R1:** LangSmith (when tracing env is on).  
**Also available:** MLflow (optional extra), or `none`.

---

## 1. Design (Strategy + Facade)

```text
MetadataAgent.invoke(state, config=…)
        │
        ▼
ObservabilityProvider.merge_invoke_kwargs(base_config)
        │
        ├─ LangSmithObservability  → LangChain/LangGraph run tags + tracing env
        ├─ MLflowObservability     → experiment + tags (+ optional autolog)
        └─ NoOpObservability       → correlation tags only
```

| Package | Role |
|---------|------|
| **`edim-dde-ai`** | `ObservabilityProvider` protocol, NoOp / LangSmith / MLflow adapters, registry |
| **`edim-dde-api`** | `configure_observability_from_env()` on lifespan; passes `request_id` on invoke |
| **`edim-dde-domain`** | No vendor SDK — product agents stay free of tracing imports |

All agents (HTTP, CLI, plugins, `invoke_agent` children) go through `MetadataAgent.invoke`, which calls the active provider — **Facade** over LangGraph config enrichment.

---

## 2. Flow in a request

```text
POST /api/v1/rca/analyze
  → build_run_config(agent_id, request_id)
  → provider.merge_invoke_kwargs(…)
  → agent.invoke(state, config=merged)
  → LangSmith/MLflow receives spans (side channel)
  → API returns RcaResponse (business path unchanged)
```

Observability is a **side channel**: failures to configure at startup fall back to no-op; they must not block `/health`.

---

## 3. Choosing a backend

```bash
EDIM_OBSERVABILITY=langsmith   # or mlflow | none | auto
```

| Value | Behavior |
|-------|----------|
| `langsmith` | Enrich LangGraph config for LangSmith; ensure `LANGCHAIN_TRACING_V2=true` if unset |
| `mlflow` | Set experiment + tags; optional `mlflow.langchain.autolog` · requires `pip install 'edim-dde-ai[mlflow]'` |
| `none` | Correlation tags only (`request_id`, `env`) — no external SaaS |
| `auto` | LangSmith if tracing env on, otherwise none |

`/health` reports the active backend name under `observability`.

---

## 4. Programmatic selection

```python
from edim_dde_ai import set_observability_provider, configure_observability_from_env
from edim_dde_ai.observability import LangSmithObservability, NoOpObservability

configure_observability_from_env()
# or:
set_observability_provider(LangSmithObservability())
```

Custom backends: implement `ObservabilityProvider` and call `set_observability_provider(...)`.

---

## 5. LangSmith (recommended)

Hands-on setup: **[LangSmith setup](langsmith-setup.md)** (next page).

```bash
EDIM_OBSERVABILITY=langsmith
EDIM_ENV=dev
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=edim-dde-dev
```

---

## 6. MLflow (optional)

Use when your org standardizes on MLflow / Databricks experiment tracking. Agent-level prompt debugging is still stronger in LangSmith.

```bash
pip install 'edim-dde-ai[mlflow]'
EDIM_OBSERVABILITY=mlflow
EDIM_MLFLOW_EXPERIMENT=edim-dde
# MLFLOW_TRACKING_URI=databricks
```

Built-in registry = **one** active provider. A composite provider can be added later if needed.

---

## 7. Correlation fields

| Field | Source |
|-------|--------|
| `request_id` | `X-Request-Id` or generated UUID |
| `edim_env` | `EDIM_ENV` |
| `agent_id` | Agent definition |
| `observability` | Backend name in metadata |

---

## 8. Relation to other planes

| Plane | Doc |
|-------|-----|
| Architecture flow | [Config → observability](../architecture/config-to-observability.md) |
| Control plane | [State store](state-store.md) |
| Knowledge | [Retrieval & RAG](retrieval-and-rag.md) |
| Env catalog | [Environment variables](../reference/env-vars.md) |

---

← [PII guardrails](pii-guardrails.md) · [Guide home](../README.md) · [LangSmith setup](langsmith-setup.md) →
