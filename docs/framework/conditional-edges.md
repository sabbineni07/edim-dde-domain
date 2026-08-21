# Conditional edges

**Learning path:** D4 · [Preface](../README.md)  
**← Previous:** [Nodes and routers](nodes-and-routers.md) · **Next:** [Content and LLM](content-and-llm.md) →

## Chapter summary

How **routers** return labels after a node and LangGraph selects the next step from `mapping`, including sugar forms (`then`/`else`, `switch`/`cases`).

**Outcome:** you can author branching graphs without custom Python edge code.

---

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

## Summary

- Conditional edges are declarative; routers stay allowlisted.
- See framework examples for sugar and multi-way switches.

**Next →** [Content and LLM (D5)](content-and-llm.md)

<!-- edim-learning-nav -->
---

← [Nodes and routers](nodes-and-routers.md) · [Preface](../README.md) · [Content and LLM](content-and-llm.md) →
