# Orchestration topology (D6)

**Learning path:** D6 · [Guide home](../README.md)  
**← Previous:** [Content and LLM](content-and-llm.md) · **Next:** [Sources and SQL](../domain/sources-and-sql.md) →

How multi-agent composition works without breaking the “one LangGraph per agent” rule.

---

## 1. Rule

**One LangGraph per agent.** Compose multi-agent behavior with an allowlisted **`invoke_agent`** node (subgraph / agent-to-agent call), not ad-hoc Python in YAML.

```text
parent.agent.yaml
  nodes:
    - prepare
    - call_rca:   type: invoke_agent   → spark_rca
    - summarize
```

---

## 2. Design patterns

| Pattern | Role |
|---------|------|
| **Composite** (structural) | Parent graph treats child agent as a node |
| **Facade** | `create_agent(child_id).invoke` hides child graph internals |
| **Template Method** | Child still runs through `MetadataAgent.invoke` |
| **Guard** | `max_depth` + refuse direct self-call |

```text
Parent MetadataAgent
  → invoke_agent node
       → create_agent(target)     # Factory Method
       → child.invoke(subset)     # depth contextvar++
       → map outputs into parent state
```

---

## 3. `invoke_agent` node

| Config key | Required | Meaning |
|------------|----------|---------|
| `agent_id` | yes | Target registered agent |
| `input_keys` | no | List of state keys to pass (default: all) |
| `output_map` | no | Map `child_key` → `parent_key` for results merged into parent state |
| `max_depth` | no | Max nested invoke depth (default `3`) |

Cycle / depth protection uses a contextvar stack. Exceeding `max_depth` raises an error. Direct `A → A` self-call is refused.

Child YAML stays a separate file — the parent only **references** `agent_id`.

---

## 4. Example

See `edim-dde-ai/examples/agents/invoke_agent_parent.agent.yaml` and `invoke_agent_child.agent.yaml`.

---

## 5. Not in Phase 0

- Cross-agent long-term memory  
- Capability-based router across a marketplace of agents (Phase 4+)  
- HITL interrupt nodes  

---

← [Content and LLM](content-and-llm.md) · [Guide home](../README.md) · [Sources and SQL](../domain/sources-and-sql.md) →
