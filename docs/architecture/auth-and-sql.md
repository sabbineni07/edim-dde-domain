# Auth and SQL

**Learning path:** B7 · [Guide home](../README.md)
**← Previous:** [Request flow](request-flow.md) · **Next:** [Config → observability](config-to-observability.md) →

**This page covers:** how code resolves a Databricks SQL warehouse token, and how Foundry authenticates.

**Not on this page:**

| Topic | Go to |
|-------|--------|
| Identities U / A / B by host | [Access & permissions](../platform/access-and-permissions.md) |
| Visual auth flows (all services) | [Authentication flows](../platform/authentication-flows.md) |
| Key Vault / `EDIM_KV_SECRET_MAP` | [Key Vault bootstrap](../platform/key-vault-bootstrap.md) |
| ACA MI warehouse + UC grant steps | [Deploy & hosting §6.4](../api/deploy-and-hosting.md#64-aca-sql-grant-managed-identity-warehouse-uc) |

---

## SQL warehouse token resolution (all hosts)

Code: `edim_dde_domain.sources.auth.resolve_access_token`

1. **Request-scoped user OAuth** — if API binds `X-Forwarded-Access-Token` (Databricks Apps)  
2. Else **`DefaultAzureCredential`** — local `az login`, ACA managed identity  

On **Databricks Apps**, step 2 is disabled by default (fail closed): without the forwarded user token you get a clear 503. The App also needs User authorization scope **`sql`** or OpenSession fails even when the header is present.

`Authorization: Bearer` is **not** treated as a Databricks user token.  
Diagnostics: `GET /api/v1/debug/sql-auth` (booleans only).

Do **not** put the Foundry SP in `AZURE_CLIENT_*` — that makes SQL’s `DefaultAzureCredential` reuse Foundry. Use `EDIM_FOUNDRY_*` instead.

| Host | Typical SQL identity |
|------|----------------------|
| Local machine | Your user via `az login` |
| Databricks Apps | Signed-in **user** (forwarded token) |
| Azure Container Apps | Container **managed identity** |

## Foundry / Azure OpenAI LLM

| Host | Auth |
|------|------|
| Local | `az login` if `EDIM_FOUNDRY_*` unset; else SP from `.env` / KV |
| Databricks Apps / ACA | Foundry **workload SP** in `EDIM_FOUNDRY_*` (KV bootstrap or host secrets) |

Foundry uses `ClientSecretCredential` when `EDIM_FOUNDRY_*` is set; otherwise `DefaultAzureCredential`.

**Do not confuse** the Databricks **App SP** (opens KV) with the **Foundry SP** (calls the model). See [Access & permissions](../platform/access-and-permissions.md).

## Sources

Named connections in `sources.yaml` (no secrets inline). Host/path support `${ENV}` interpolation. Runtime resolves a token via the paths above.

See [domain sources and SQL](../domain/sources-and-sql.md) and the deep dive [DESIGN_SOURCES_AND_SQL_NODES.md](../DESIGN_SOURCES_AND_SQL_NODES.md).

<!-- edim-learning-nav -->
---

← [Request flow](request-flow.md) · [Guide home](../README.md) · [Config → observability](config-to-observability.md) →
