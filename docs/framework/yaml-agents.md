# YAML agents

**Learning path:** D2 · [Guide home](../README.md)
**← Previous:** [YAML schema](yaml-schema.md) · **Next:** [Nodes and routers](nodes-and-routers.md) →


Agents are declared as `*.agent.yaml` and loaded with:

```python
from edim_dde_ai import register_from_yaml, register_from_directory, create_agent

register_from_yaml("path/to/demo.agent.yaml")
# or recursive:
register_from_directory("agents", recursive=True, overwrite=True)

agent = create_agent("demo")
agent.invoke({"x": 1})
```

## Document shape (essentials)

```yaml
agent_id: demo
display_name: Demo
version: 1
entry: {method: invoke, sync: true}
content_dir: ./content          # optional
graph:
  nodes: [...]
  edges: [[START, a], [a, END]]
  conditional_edges: [...]      # optional
  routes: [...]                 # optional sugar → conditional_edges
```

- `START` / `END` are reserved edge endpoints  
- Prefer `[START, entry_node]` or set `graph.entry`  
- Node `type` must be registered before `create_agent` builds the graph  

Compiled agents are **cached** after first `create_agent`; re-registering YAML invalidates that id.

## Optional `bindings` (Phase 1 LLM; search/cosmos/sql-warehouse documented)

Per-agent infra targets without forking process globals. See [YAML schema — bindings](yaml-schema.md#bindings-phase-1--llm-wired-search--cosmos--sql-warehouse-documented).

```yaml
bindings:
  llm:
    endpoint: ${ENV:AZURE_OPENAI_ENDPOINT}
    deployment: ${ENV:AZURE_OPENAI_DEPLOYMENT_NAME}
    temperature: 0.0
    top_p: 1.0
    top_k: 40
    max_tokens: 4096
  search:
    endpoint: ${ENV:EDIM_AZURE_SEARCH_ENDPOINT}
    index: ${ENV:EDIM_AZURE_SEARCH_INDEX}
  cosmos:
    endpoint: ${ENV:EDIM_COSMOS_ENDPOINT}
    database: ${ENV:EDIM_COSMOS_DATABASE}
  sql-warehouse:
    host: ${ENV:DATABRICKS_HOST}
    http_path: ${ENV:DATABRICKS_HTTP_PATH}
```

More detail: `edim-dde-ai/docs/USAGE.md` · `edim-dde-ai/docs/DESIGN.md`

<!-- edim-learning-nav -->
---

← [YAML schema](yaml-schema.md) · [Guide home](../README.md) · [Nodes and routers](nodes-and-routers.md) →
