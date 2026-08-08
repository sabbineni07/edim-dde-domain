# Environments (BL-046)

**Learning path:** C1 · [Guide home](../README.md)
**← Previous:** [Config → observability](../architecture/config-to-observability.md) · **Next:** [Security baseline](security-baseline.md) →


**Phase 0 focus:** `SDBX`, `DEV`, `PROD`  
**Documented for later:** `UAT`, `INTG`

Set `EDIM_ENV` to one of: `sdbx` | `dev` | `uat` | `intg` | `prod`.

---

## Matrix (Phase 0)

| Concern | SDBX | DEV | PROD |
|---------|------|-----|------|
| Purpose | Spikes, LangSmith learning | Active development | Live Apps traffic |
| `EDIM_ENV` | `sdbx` | `dev` | `prod` |
| Databricks workspace | Sandbox | Shared DEV | Production |
| SQL tables | Sample / synthetic UC | DEV UC FQNs | Prod UC FQNs |
| Azure OpenAI deployment | Non-prod | DEV deployment | Prod deployment |
| Key Vault (convention) | `edim-dde-sdbx-kv` | `edim-dde-dev-kv` | `edim-dde-prod-kv` |
| LangSmith project | `edim-dde-sdbx` | `edim-dde-dev` | `edim-dde-prod` |
| State store (typical) | `postgres` or `memory` | `postgres` | **`cosmos`** |
| Retrieval (typical) | `faiss` or `memory` | `faiss` / Azure | **`azure_ai_search`** |
| Tracing verbosity | High OK | On | On + PII redaction |
| Agent YAML changes | Experimental OK | Feature branches | Approved versions only |
| Foundry auth | `az login` or SP | SP or `az login` | **SP from Key Vault** |

---

## Deferred environments

| Env | Purpose (later) |
|-----|-----------------|
| **UAT** | Business acceptance before PROD |
| **INTG** | Cross-system integration tests |

Do not invent ad-hoc env names. Extend this matrix when UAT/INTG are stood up.

---

## Promotion path (Phase 0 simplified)

```text
SDBX  →  DEV  →  PROD
                 (UAT / INTG inserted later)
```

Promotion checklist (manual for Phase 0):

1. YAML validates (`edim-dde-ai` schema)
2. Unit / e2e tests green
3. LangSmith spot-check of a successful run
4. Secrets present in target Key Vault
5. Table FQNs and Foundry deployment confirmed for target env

**Hosting:** first cut = **Databricks Apps**; portable Docker image for Azure Container Apps — see [Deploy & hosting](../api/deploy-and-hosting.md).

---

## Required env vars by environment

See [Environment variables](../reference/env-vars.md) and [.env.example](../../.env.example).

Minimum for agent invoke:

- Databricks: `DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH`, table FQNs
- Foundry: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`
- LangSmith (recommended): `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`
- State store (recommended local): `EDIM_STATE_STORE=postgres` + `EDIM_DATABASE_URL` — see [state-store.md](state-store.md)
- Retrieval (optional local): `EDIM_RETRIEVAL=faiss` + `EDIM_FAISS_INDEX_PATH` — see [retrieval-and-rag.md](retrieval-and-rag.md)
- Platform: `EDIM_ENV`, optional `AZURE_KEY_VAULT_URL` + secret name mappings

<!-- edim-learning-nav -->
---

← [Config → observability](../architecture/config-to-observability.md) · [Guide home](../README.md) · [Security baseline](security-baseline.md) →
