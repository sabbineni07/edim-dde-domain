# Testing

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
