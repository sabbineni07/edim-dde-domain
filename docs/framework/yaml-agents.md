# YAML agents

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

More detail: [edim-dde-ai USAGE](../../../edim-dde-ai/docs/USAGE.md) · [DESIGN](../../../edim-dde-ai/docs/DESIGN.md)
