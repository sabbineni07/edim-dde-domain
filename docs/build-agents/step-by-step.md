# New agent — step by step

**Learning path:** F2 · [Guide home](../README.md)
**← Previous:** [Agent package layout](agent-package-layout.md) · **Next:** [External plugins](external-plugins.md) →


## 1. Create the package

Under `edim-dde-domain/src/edim_dde_domain/agents/` (bundled) **or** an [external plugin](external-plugins.md) directory:

```text
agents/my_agent/
  __init__.py
  my_agent.agent.yaml
  nodes.py
  logic.py
```

## 2. Write the YAML graph

Minimal skeleton:

```yaml
agent_id: my_agent
display_name: My Agent
version: 1
entry:
  method: invoke
  sync: true

graph:
  nodes:
    - id: start
      type: passthrough
    - id: finish
      type: echo_result
      from_fields: [hello]
  edges:
    - [START, start]
    - [start, finish]
    - [finish, END]
```

Add `domain.sql.query` nodes for UC reads; use `skip_if_key` / existing `output_key` for test overrides.

## 3. Implement logic + nodes

`logic.py`:

```python
def greet(state: dict) -> dict:
    return {"hello": "world"}
```

`nodes.py`:

```python
from edim_dde_ai import register_node
from edim_dde_domain.agents.my_agent import logic

@register_node("domain.my.greet")
def greet_factory(_config):
    def _node(state):
        return logic.greet(state)
    return _node
```

Wire `type: domain.my.greet` in YAML.

## 4. Optional helpers and content

- Extract pure rules into `helpers/` when tests don’t need the full graph
- Add `content_dir: ./content` + prompts/skills for `llm_chain`

## 5. Bootstrap discovery

**Bundled:** place under domain `agents/`; `bootstrap_agents()` imports `*/nodes.py` and registers nested `*.agent.yaml` automatically — no hardcoded path edits.

**External:** set `EDIM_AGENT_DIRS` or call `load_external_agents([...])`.

## 6. Expose via API (optional)

Add a route in `edim-dde-api` that:

1. Validates a request model  
2. `create_agent("my_agent").invoke(...)` (prefer `asyncio.to_thread`)  
3. Maps state → a **response** Pydantic model (do not return raw state)

## 7. Test

- Unit-test helpers without SQL/LLM  
- E2E with overrides (`metrics` / `evidence_pack`) + `DomainStubLLM`  
- Optional `TestClient` for HTTP

See [testing](../contribute/testing.md).

<!-- edim-learning-nav -->
---

← [Agent package layout](agent-package-layout.md) · [Guide home](../README.md) · [External plugins](external-plugins.md) →
