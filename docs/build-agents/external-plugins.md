# External agent plugins

**Learning path:** F3 · [Guide home](../README.md)
**← Previous:** [Step-by-step](step-by-step.md) · **Next:** [API configuration](../api/configuration.md) →


Bundled agents ship inside the `edim-dde-domain` wheel. Additional agents register **into the same registries** without forking the package.

## Directory plugins (`EDIM_AGENT_DIRS`)

Layout matches bundled agents (recursive `*.agent.yaml` + optional `nodes.py`):

```bash
export EDIM_AGENT_DIRS=/opt/edim-agents/acme,/opt/edim-agents/partner
```

`bootstrap_agents()` loads these by default. Or:

```python
from edim_dde_domain import bootstrap_agents, load_external_agents

bootstrap_agents(load_external=False)
load_external_agents(["/opt/edim-agents/acme"], entry_points=False)
```

## Packaging entry points

In the plugin wheel’s `pyproject.toml`:

```toml
[project.entry-points."edim_dde.agents"]
acme = "acme_edim_agents:register"
```

```python
# acme_edim_agents/__init__.py
from pathlib import Path
from edim_dde_ai import register_from_directory

def register() -> None:
    import acme_edim_agents.nodes  # noqa: F401
    register_from_directory(Path(__file__).parent, recursive=True, overwrite=True)
```

Install the plugin into the same environment as the API; bootstrap loads the entry-point group `edim_dde.agents`.

## Rules

- Namespace node type ids (`acme.*`) — don’t collide with `domain.*`
- Reuse `domain.sql.query` and domain sources when talking to Databricks
- No secrets in YAML

<!-- edim-learning-nav -->
---

← [Step-by-step](step-by-step.md) · [Guide home](../README.md) · [API configuration](../api/configuration.md) →
