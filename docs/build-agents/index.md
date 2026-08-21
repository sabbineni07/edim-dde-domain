# Part F — Build agents

**Learning path:** F0 · [Preface](../README.md)  
**← Previous:** [External add-ons](../domain/external-addons.md) · **Next:** [Package layout](agent-package-layout.md) →

## Chapter summary

Part F is the **authoring handbook**: directory layout, registration, and plugin discovery for new YAML agents. Follow this part when adding agents beyond the bundled tuning and RCA graphs.

**After completing Part F you will:**

- Scaffold an `agents/<agent_id>/` package.
- Register node types and bootstrap the agent into the runtime catalog.
- Load optional agent directories via `EDIM_AGENT_DIRS`.

---

## Prerequisites

| Requirement | Chapter |
|-------------|---------|
| YAML schema | [YAML schema (D1)](../framework/yaml-schema.md) |
| Bundled agent examples | [Cluster tuning (E3b)](../domain/cluster-tuning-agent.md) |

---

## Chapters in this part

| Step | Chapter | Topic |
|------|---------|-------|
| **F1** | [Package layout](agent-package-layout.md) | Directory contract |
| **F2** | [Step-by-step](step-by-step.md) | Authoring checklist |
| **F3** | [External plugins](external-plugins.md) | `EDIM_AGENT_DIRS` |

---

## Authoring checklist (summary)

1. Create `agents/<id>/<id>.agent.yaml` + `nodes.py` (+ optional `logic.py`, `content/`).
2. Register node factories with `@register_node("your.type")`.
3. Add bootstrap import in domain `bootstrap.py` (or plugin path).
4. Add tests in `edim-dde-domain/tests/` mirroring bundled agents.
5. Expose via API route only when the agent is product-ready.

!!! tip "Pro tip"
    Copy structure from `cluster_tuning` or `spark_rca` and delete product-specific nodes incrementally — faster than scaffolding from empty YAML.

---

## Summary

**F1 → F2 → F3** is the recommended sequence for first-time agent authors.

**Next →** [Package layout (F1)](agent-package-layout.md)
