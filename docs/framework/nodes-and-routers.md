# Nodes and routers

## Nodes

Factory shape: `(config) -> (state) -> partial_updates`.

```python
from edim_dde_ai import register_node

@register_node("domain.my.step")
def step_factory(config: dict):
    def _node(state: dict) -> dict:
        return {"out": state.get("in")}
    return _node
```

Builtins: `passthrough`, `set_value`, `echo_result`, `llm_chain`.

## Routers

Used by `conditional_edges`. Factory: `(config) -> (state) -> branch_label`.

Builtins include `field_truthy`, `field_equals`, `field_in`, `field_compare`, `choice`.

See [conditional edges](conditional-edges.md).
