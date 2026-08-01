# Orchestration topology (BL-025)

## Rule

**One LangGraph per agent.** Compose multi-agent behavior with an allowlisted **`invoke_agent`** node (subgraph / agent-to-agent call), not ad-hoc Python in YAML.

```text
parent.agent.yaml
  nodes:
    - prepare
    - call_rca:   type: invoke_agent   → spark_rca
    - summarize
```

---

## `invoke_agent` node

| Config key | Required | Meaning |
|------------|----------|---------|
| `agent_id` | yes | Target registered agent |
| `input_keys` | no | List of state keys to pass (default: all) |
| `output_map` | no | Map `child_key` → `parent_key` for results merged into parent state |
| `max_depth` | no | Max nested invoke depth (default `3`) |

Cycle / depth protection uses a contextvar stack. Exceeding `max_depth` raises an error.

---

## Example

See `edim-dde-ai/examples/agents/invoke_agent_parent.agent.yaml` and `invoke_agent_child.agent.yaml`.

---

## Not in Phase 0

- Cross-agent long-term memory
- Capability-based router across a marketplace of agents (Phase 4+)
- HITL interrupt nodes
