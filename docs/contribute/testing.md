# Testing

**Learning path:** H4 · [Guide home](../README.md)
**← Previous:** [Glossary](../reference/glossary.md) · **Next:** [Guide home](../README.md) →


## Packages

```bash
cd edim-dde-ai && pytest -q
cd edim-dde-domain && pytest -q
cd edim-dde-api && pytest -q
```

## Patterns

| Pattern | Use |
|---------|-----|
| **Helper unit tests** | No SQL/LLM (sizing, guardrails, evidence_pack) |
| **Metrics / evidence_pack overrides** | Skip live SQL in agent e2e |
| **`DomainStubLLM`** | `edim_dde_domain.testing` — deterministic offline LLM |
| **`TestClient`** | HTTP `/health` and `/api/v1/*` in api tests |
| **`reset_bootstrap()`** | Allow re-register in fixtures |

Do **not** put production SQL/LLM stubs in main packages.

## Live / dry smoke (beyond pytest)

For a shared engineer runbook (what info to gather, where to configure, dry vs live vs remote):

→ **[Live & dry smoke test](live-smoke-test.md)**

<!-- edim-learning-nav -->
---

← [Glossary](../reference/glossary.md) · [Guide home](../README.md) · [Live smoke](live-smoke-test.md) →
