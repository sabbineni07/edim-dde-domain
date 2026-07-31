# Auth and SQL

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
| **Prod** | `AZURE_TENANT_ID` + `AZURE_CLIENT_ID` + `AZURE_CLIENT_SECRET` (inject from Key Vault → env) |

## Sources

Named connections in `sources.yaml` (no secrets inline). Host/path support `${ENV}` interpolation. Runtime resolves a token via the paths above.

See [domain sources and SQL](../domain/sources-and-sql.md) and the deep dive [DESIGN_SOURCES_AND_SQL_NODES.md](../DESIGN_SOURCES_AND_SQL_NODES.md).
