# Core concepts (A2)

**Learning path:** A2 · [Guide home](../README.md)  
**← Previous:** [Quickstart](quickstart.md) · **Next:** [End-to-end design](../architecture/end-to-end-design.md) →

Vocabulary and mental models used everywhere else in this guide.

---

## 1. Agent

A named graph identified by `agent_id` (e.g. `cluster_tuning`, `spark_rca`). Declared in `*.agent.yaml`, registered into `edim-dde-ai`, invoked as:

```python
from edim_dde_ai import create_agent
final_state = create_agent("cluster_tuning").invoke({...})
```

**Patterns:** Registry (definition by id) + Factory Method (`create_agent`).

---

## 2. Node

A step in the graph. YAML references a **type id** string; Python registers a factory with `@register_node("type.id")`.

| Kind | Examples |
|------|----------|
| Framework builtins | `passthrough`, `set_value`, `echo_result`, `llm_chain`, `invoke_agent`, `rag.retrieve` |
| Shared domain | `domain.sql.query` |
| Product / plugin | `domain.tuning.*`, `domain.rca.*`, `acme.*` |

**Pattern:** Strategy — the `type` id selects the algorithm; YAML never embeds import paths.

```yaml
- id: synthesize
  type: llm_chain
  chain: rca
  output_key: llm_raw
```

```python
@register_node("domain.rca.classify_failure")
def classify_failure_factory(_config: dict):
    def _node(state: dict) -> dict:
        return logic.classify_failure(state)
    return _node
```

---

## 3. State

Flat `dict` in / out. Nodes return **partial updates** merged into state. No typed schema on the graph itself (API response models are separate OpenAPI DTOs).

```text
invoke({job_run_id, …})
  → node A returns {evidence_pack: …}
  → node B returns {classification_hint: …}
  → merged state continues
  → API projects result → RcaResponse / TuningResponse
```

**Pattern:** Adapter — flat dict callables adapted to LangGraph’s internal `data` bag.

---

## 4. Content

Prompts and skills for `llm_chain`, usually under `content/` next to the agent YAML (`content_dir: ./content`).

| Artifact | Path convention |
|----------|-----------------|
| System / human prompts | `content/prompts/{chain}.system.md`, `{chain}.human.md` |
| Skills | `content/skills/{name}.md` |

`{var}` placeholders are substituted from state keys.

---

## 5. Bootstrap

`edim_dde_domain.bootstrap_agents()` (API lifespan):

```text
load sources.yaml
load corpora.yaml
import agents/*/nodes.py          # @register_node factories
register nested *.agent.yaml
load external plugins             # EDIM_AGENT_DIRS / entry points
```

Hosts also:

1. `configure_observability_from_env()`
2. `configure_state_store_from_env()`
3. `configure_retrieval_from_env()`
4. `sync_registered_agents_to_store()`
5. `set_llm_provider(...)` (API: lazy Foundry)

---

## 6. Hybrid model

| Layer | Owns |
|-------|------|
| YAML | Topology, SQL text, node config, edges, optional `rag` / `metadata` |
| Python | Node factories + pure helpers (`logic.py`, `helpers/`) |

YAML never embeds arbitrary Python import paths — only allowlisted type ids.

---

## 7. Planes (preview)

| Plane | Examples |
|-------|----------|
| Source control | Git `*.agent.yaml`, prompts, runbooks |
| Control plane | StateStore catalog / sessions / audit |
| Knowledge | RetrievalProvider indexes |
| Data plane | LangGraph + SQL + Foundry |
| Observability | LangSmith / MLflow |

Full treatment: **[End-to-end design](../architecture/end-to-end-design.md)** (next page).

---

## 8. Overrides

| Request field | Effect |
|---------------|--------|
| `metrics` (tuning) | Skip SQL collect for metrics |
| `evidence_pack` (RCA) | Skip SQL collectors |

LLM nodes still run unless you stub the provider (tests).

---

← [Quickstart](quickstart.md) · [Guide home](../README.md) · [End-to-end design](../architecture/end-to-end-design.md) →
