# Nodes and routers (D3)

**Learning path:** D3 · [Guide home](../README.md)  
**← Previous:** [YAML agents](yaml-agents.md) · **Next:** [Conditional edges](conditional-edges.md) →

How allowlisted **node types** and **routers** work — the Strategy + Registry core of the framework.

---

## 1. Design patterns

| Pattern | Role here |
|---------|-----------|
| **Registry** | `type` id → factory catalog (`register_node` / `register_router`) |
| **Strategy** | Each factory returns a different algorithm selected by YAML `type` / `router` |
| **Factory Method** | `(config) -> callable` builds the per-node Strategy |
| **Adapter** | Flat `(state)->partial` adapted into LangGraph’s `data` bag by `GraphBuilder` |

```text
YAML type: "domain.rca.classify_failure"
        │
        ▼
get_node_factory(type)     # Registry lookup
        │
        ▼
factory(config) → _node    # Factory Method
        │
        ▼
adapt_node(_node)          # Adapter → LangGraph
```

---

## 2. Nodes

Factory shape: `(config) -> (state) -> partial_updates`.

```python
from edim_dde_ai import register_node

@register_node("domain.my.step")
def step_factory(config: dict):
    key = config.get("output_key", "out")
    def _node(state: dict) -> dict:
        return {key: state.get("in")}
    return _node
```

### Builtin node types (`edim-dde-ai`)

| Type id | Role |
|---------|------|
| `passthrough` | No-op |
| `set_value` | Set a field (literal or `{template}`) |
| `echo_result` | Build `result` from listed fields |
| `llm_chain` | Prompts + skills + LLMProvider / chain invoker |
| `invoke_agent` | Nested agent call (depth-limited) |
| `rag.retrieve` | Similarity / hybrid search via RetrievalProvider |

### Domain / product types

| Type id | Role |
|---------|------|
| `domain.sql.query` | Named-source SQL collect |
| `domain.tuning.*` | cluster_tuning steps |
| `domain.rca.*` | spark_rca steps (incl. `build_retrieval_query`) |

Full catalog: [node type ids](../reference/node-type-ids.md).

**Security:** YAML cannot invent type ids. Unregistered types fail at graph build.

---

## 3. Routers

Used by `conditional_edges`. Factory: `(config) -> (state) -> branch_label`.

Builtins: `field_truthy`, `field_equals`, `field_in`, `field_compare`, `choice`.

```yaml
conditional_edges:
  - source: generate_recommendation
    router: field_truthy
    config:
      field: include_explanation
    mapping:
      yes: generate_explanation
      no: END
```

Detail: [conditional edges](conditional-edges.md).

---

## 4. Config merge rule

For each YAML node, every key except `id` and `type` becomes `config` passed to the factory (`core/definition.py`). Example:

```yaml
- id: retrieve_runbooks
  type: rag.retrieve
  corpus: spark-runbooks
  top_k: 5
  query_key: retrieval_query
```

→ `rag_retrieve_factory({"corpus": "spark-runbooks", "top_k": 5, ...})`.

`GraphBuilder` also injects `agent_id` for content resolution on `llm_chain`.

---

← [YAML agents](yaml-agents.md) · [Guide home](../README.md) · [Conditional edges](conditional-edges.md) →
