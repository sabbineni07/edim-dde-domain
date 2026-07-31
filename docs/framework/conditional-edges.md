# Conditional edges

After a node, a **router** returns a label; LangGraph picks the next node from `mapping`.

## Explicit form

```yaml
conditional_edges:
  - source: decide
    router: field_truthy
    config:
      field: include_details
    mapping:
      "yes": details
      "no": summary
```

## Routes sugar

Author-friendly form desugars to `conditional_edges` at parse time (`routes_sugar.py`):

```yaml
routes:
  - after: decide
    when:
      field: include_details
      op: truthy
    then: details
    else: summary
```

Also supports `equals` / `in` / `compare` and multi-way `switch` / `cases`.

Examples in `edim-dde-ai/examples/agents/conditional_agent.agent.yaml` and `routes_sugar_agent.agent.yaml`.
