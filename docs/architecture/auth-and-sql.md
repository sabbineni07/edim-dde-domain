# Auth and SQL

**Learning path:** B7 · [Guide home](../README.md)
**← Previous:** [Request flow](request-flow.md) · **Next:** [Config → observability](config-to-observability.md) →


## SQL warehouse (two paths only)

| Environment | How the token is obtained |
|-------------|---------------------------|
| **Local** | `az login` → `DefaultAzureCredential` |
| **Databricks Apps** | Gateway sends `X-Forwarded-Access-Token` → API middleware → ContextVar → SQL connector |

`Authorization: Bearer` is **not** treated as a Databricks user token (reserved for future API auth).

## Foundry / Azure OpenAI LLM

| Environment | Auth |
|-------------|------|
| **Local** | `az login` (leave `AZURE_CLIENT_*` unset) |
| **Prod / Apps** | Foundry **workload SP** in `AZURE_CLIENT_*` — often loaded from Key Vault at startup |

**Important:** On Databricks Apps, the identity that **opens** Key Vault (App SP) is **not** the same as the Foundry SP. See [Access & permissions](../platform/access-and-permissions.md).

## Sources

Named connections in `sources.yaml` (no secrets inline). Host/path support `${ENV}` interpolation. Runtime resolves a token via the paths above.

See [domain sources and SQL](../domain/sources-and-sql.md) and the deep dive [DESIGN_SOURCES_AND_SQL_NODES.md](../DESIGN_SOURCES_AND_SQL_NODES.md).

<!-- edim-learning-nav -->
---

← [Request flow](request-flow.md) · [Guide home](../README.md) · [Config → observability](config-to-observability.md) →
