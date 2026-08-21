# Testing (H4)

**Learning path:** H4 · [Preface](../README.md)  
**← Previous:** [Glossary](../reference/glossary.md) · **Next:** [Live smoke](live-smoke-test.md) →

## Chapter summary

How to run **`pytest`** across `edim-dde-ai`, `edim-dde-domain`, and `edim-dde-api`. Unit tests are the first gate before dry/live smoke.

**Outcome:** all three packages green offline with stubs where required.

---

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

→ **[Live & dry smoke test](live-smoke-test.md)** · **[Windows checklist](windows-smoke-checklist.md)**  
→ Workspace root **[VALIDATION.md](../../../VALIDATION.md)** — numbered test suite (pytest + framework examples + dry/live HTTP + HITL + quality). Use that when running the full stack from another laptop.

<!-- edim-learning-nav -->
---

← [Glossary](../reference/glossary.md) · [Preface](../README.md) · [Live smoke](live-smoke-test.md) →
