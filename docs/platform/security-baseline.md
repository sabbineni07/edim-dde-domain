# Security baseline (BL-013)

**Learning path:** C2 · [Guide home](../README.md)
**← Previous:** [Environments](environments.md) · **Next:** [Access & permissions](access-and-permissions.md) →


**Phase 0 decision:** Keep the **current identity model**. Add **Azure Key Vault SDK** bootstrap for secrets. Document a **role matrix** for later enforcement.

For **who opens Key Vault vs who calls Foundry vs who runs SQL**, and Databricks Apps step-by-step, see:

→ **[Access & permissions](access-and-permissions.md)** (Identities U / A / B, diagrams, IAM checklist)

---

## What “role matrix only (docs)” means

| Approach | Meaning |
|----------|---------|
| **Docs / matrix only (Phase 0)** | We **name** roles (`invoke`, `operate`, `administer`, `approve_tools`) and describe who should have them. The API does **not** yet check JWT role claims or reject callers by role. |
| **Enforcement (later)** | Middleware or gateway would require a role claim before invoke / admin / tool-approve actions. |

Phase 0 still **enforces identity** for SQL and Foundry (user token / Azure AD / SP). It does **not** yet enforce fine-grained application roles.

---

## Identity model (unchanged)

| Target | Local / SDBX | Apps / PROD |
|--------|--------------|-------------|
| Databricks SQL | `az login` → `DefaultAzureCredential` | `X-Forwarded-Access-Token` via API middleware |
| Azure AI Foundry | `az login` → `DefaultAzureCredential` | Service principal (`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`) loaded from **Key Vault** |

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

## Key Vault SDK bootstrap (summary)

When `AZURE_KEY_VAULT_URL` is set, API startup loads mapped secrets into process environment.

| Env var | Purpose |
|---------|---------|
| `AZURE_KEY_VAULT_URL` | Vault URI, e.g. `https://edim-dde-dev-kv.vault.azure.net/` |
| `EDIM_KV_SECRET_MAP` | Optional `vaultSecret:ENV_VAR` pairs |
| `AZURE_TENANT_ID` | Required when using Databricks Apps SP to open the vault |
| `EDIM_KV_FORCE` | `1` = overwrite existing env from vault |
| `EDIM_KV_CLIENT_*` | Optional dedicated vault-reader SP (overrides Apps SP) |

**Vault auth order:** `EDIM_KV_CLIENT_*` → `DATABRICKS_CLIENT_*` (Apps SP) → `DefaultAzureCredential`.

Default secret map: `azure-client-id` → `AZURE_CLIENT_ID`, etc. Full design and IAM steps: [Access & permissions](access-and-permissions.md).

---

## Related

- [**Access & permissions**](access-and-permissions.md) — identities, KV, Apps
- [PII guardrails](pii-guardrails.md)
- [Auth and SQL](../architecture/auth-and-sql.md)
- [Environments](environments.md)

<!-- edim-learning-nav -->
---

← [Environments](environments.md) · [Guide home](../README.md) · [Access & permissions](access-and-permissions.md) →
