# Nodes and routers (D3)

**Learning path:** D3 · [Preface](../README.md)  
**← Previous:** [YAML agents](yaml-agents.md) · **Next:** [Conditional edges](conditional-edges.md) →

## Chapter summary

Allowlisted **node types** and **routers** — the Strategy + Registry core of `edim-dde-ai`. Explains how YAML `type` / `router` ids map to Python factories.

**Outcome:** you can extend the graph with a new allowlisted node without forking the builder.

---

How allowlisted **node types** and **routers** work — the Strategy + Registry core of the framework.

---

## 1. Design patterns

| Pattern | Role here |
|---------|-----------|
| **Registry** | `type` id → factory catalog (`register_node` / `register_router`) |
| **Strategy** | Each factory returns a different algorithm selected by YAML `type` / `router` |
| **Factory Method** | `(config) -> callable` builds the per-node Strategy |
| **Adapter** | Flat `(state)->partial` adapted into LangGraph’s `data` bag by `GraphBuilder` |
| **Decorator** | `skip_until_resume` wraps every node so HITL resume does not re-run work before the gate |

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
skip_until_resume(...)     # Decorator (HITL resume skip)
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
| `hitl.gate` | Pause for human approval (StateStore session). [HITL resume](hitl-resume.md) |

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

## 5. Node-local config is opaque to the framework

The framework treats every non-`id`/`type` key as an **uninterpreted payload**
for exactly one factory. It never validates, merges, or shares those keys across
nodes. This is why a generic, config-driven engine can carry arbitrarily rich
domain policy (for example `cluster_tuning`'s `resource_pressure` block) without
the platform learning anything about that domain.

What the framework guarantees (`core/definition.py` + `graph/builder.py`):

1. `id` and `type` are structural; everything else → `NodeSpec.config` (a plain
   dict).
2. At build time it only does `factory = get_node_factory(type)` then
   `factory(node.config)`.
3. It does **not** inspect, validate, or type-check domain keys. Unknown keys are
   simply whatever that one factory chooses to read.
4. Keys on one node are invisible to other nodes. There is no global config bag.

```text
node YAML
  ├── id / type          → framework (routing, registry lookup)
  └── everything else     → NodeSpec.config → ONE factory (domain interprets)
```

Consequences:

- Two nodes may use the same key name for different meanings; each factory owns
  its own vocabulary.
- Misspelled or extra keys never raise at the framework level — they are ignored
  by the factory that does not read them. Validate domain-critical keys inside
  the factory if you need strictness.
- Adding a new knob (new dimension, new threshold) is a YAML + factory change in
  the owning domain package; no framework release is required.

## 6. Config → state hand-off (how later nodes "see" a node's config)

A factory closes over config at **build time**; the returned callable runs at
**invoke time** and can only affect the graph through the **state** it returns.
So downstream nodes do not read an upstream node's YAML — they read the **state
keys** that upstream node wrote. State is the shared runtime contract; YAML
config is private to a node.

```text
build time:   factory(config)         # config captured in a closure
invoke time:  _node(state) -> partial # writes shared state keys
later nodes:  read those state keys    # never the upstream YAML
```

Worked example — `cluster_tuning`'s `prepare_sizing_payload`
(`agents/cluster_tuning/nodes.py`) reads its node-local `history_*` and
`resource_pressure` config, then writes results onto state:

| `prepare_sizing_payload` writes to state | Consumed later by |
|------------------------------------------|-------------------|
| `sizing_hints` / `sizing_hints_full` | `run_sizing` LLM prompt |
| `historical_context` | sizing + explanation prompts |
| `resource_pressure_config` | `parse_sizing` guardrail clamps, `validate_performance`, `assess_risks` |

Because the resolved policy is placed on state once, the sizing prompt, the hard
guardrail clamps, and the risk step all use the **same** thresholds without
re-reading YAML or drifting apart.

### Config that must reach non-graph consumers

Some domain consumers are not graph nodes (e.g. the `ExperienceTransform` index
parser and the `cluster_tuning.quality` evaluator registered at bootstrap).
Graph-time node config cannot reach them, so the domain package reads the same
YAML block once at bootstrap (`bootstrap._cluster_tuning_pressure_config()`) and
passes it to those registrations. That keeps offline indexing and scoring aligned
with the agent's live policy while the framework contract stays generic.

??? note "In depth (optional) — agent authors — register a domain node end-to-end"

    §5–6 above are the contract. This recipe is the checklist when adding a new
    `domain.*` type.

    1. **Choose a type id** under your pack (`domain.tuning.*`, `domain.rca.*`,
       or a new prefix). Unregistered ids fail at graph build — that is intentional.
    2. **Write a factory** in `agents/<pack>/nodes.py`:

        ```python
        @register_node("domain.my.step")
        def my_step_factory(config: dict):
            knob = config.get("my_knob", "default")
            def _node(state: dict) -> dict:
                return {"my_out": f"{knob}:{state.get('in')}"}
            return _node
        ```

    3. **Reference it from YAML** with only the knobs *this* factory reads. Extra
       keys are silently ignored by the framework.
    4. **Put shared policy on state** when later nodes or offline tools need it
       (see the `resource_pressure_config` pattern). Do not expect other factories
       to read this node's YAML.
    5. **Import the nodes module** from domain bootstrap (`_import_packaged_agent_nodes`
       already loads `agents/*/nodes.py`).
    6. **Test** the factory in isolation (config → closed-over behavior) and with a
       small graph invoke if routing depends on the new state keys.

    Prefer extending an existing node's config over inventing a new type when the
    topology does not change.

---

## Summary

- Register factories; keep business logic out of fat node adapters.
- Prefer config on existing types before inventing new type ids.

**Next →** [Conditional edges (D4)](conditional-edges.md)

← [YAML agents](yaml-agents.md) · [Preface](../README.md) · [Conditional edges](conditional-edges.md) →
