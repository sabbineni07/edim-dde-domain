# Security baseline (BL-013)

**Learning path:** C2 · [Guide home](../README.md)
**← Previous:** [Environments](environments.md) · **Next:** [Access & permissions](access-and-permissions.md) →


**Phase 0 decision:** Keep the **current identity model**. Add **Azure Key Vault SDK** bootstrap for secrets. Document a **role matrix** for later enforcement.

**Where to read next (do not mix topics here):**

| Topic | Doc |
|-------|-----|
| Identities U / A / B, host matrix | [Access & permissions](access-and-permissions.md) |
| Key Vault load + `EDIM_KV_SECRET_MAP` | [Key Vault bootstrap](key-vault-bootstrap.md) |
| ACA MI warehouse / UC grants | [Deploy & hosting §6.3](../api/deploy-and-hosting.md#63-aca-sql--grant-managed-identity-warehouse--uc) |
| Long-term end-user SSO / app permissions | Platform backlog **BL-056** (not Phase 0) |

---

## What “role matrix only (docs)” means

| Approach | Meaning |
|----------|---------|
| **Docs / matrix only (Phase 0)** | We **name** roles (`invoke`, `operate`, `administer`, `approve_tools`) and describe who should have them. The API does **not** yet check JWT role claims or reject callers by role. |
| **Enforcement (later)** | Middleware or gateway would require a role claim before invoke / admin / tool-approve actions — see platform **BL-056** (SSO + end-user entitlements). |

Phase 0 still **enforces identity** for SQL and Foundry (user token / Azure AD / SP). It does **not** yet enforce fine-grained application roles.

---

## Identity model (summary)

| Target | Local / SDBX | Apps / PROD |
|--------|--------------|-------------|
| Databricks SQL | `az login` → `DefaultAzureCredential` | `X-Forwarded-Access-Token` via API middleware |
| Azure AI Foundry | `az login` → `DefaultAzureCredential` | `EDIM_FOUNDRY_*` from Key Vault |

YAML **cannot** dynamically import Python. Node and router type ids must already be registered (allowlist).

---

## Role matrix (documented for Phase 0)

| Role | Intent | Typical holders | Enforced in Phase 0? |
|------|--------|-----------------|----------------------|
| `invoke` | Call agent HTTP APIs | App users, service callers | No (network / Apps auth only) |
| `operate` | View LangSmith, triage failures | Support / SRE | No |
| `administer` | Register agents, rotate secrets, change env config | Platform engineers | No |
| `approve_tools` | Approve side-effecting tool calls (future MCP/HITL) | Business owners | No (no MCP yet) |

---

## Related

- [Access & permissions](access-and-permissions.md) — identities by host  
- [Key Vault bootstrap](key-vault-bootstrap.md) — secret load  
- [PII guardrails](pii-guardrails.md)  
- [Auth and SQL](../architecture/auth-and-sql.md)  
- [Environments](environments.md)  

<!-- edim-learning-nav -->
---

← [Environments](environments.md) · [Guide home](../README.md) · [Access & permissions](access-and-permissions.md) →
