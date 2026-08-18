# Environments (BL-046)

**Learning path:** C1 · [Guide home](../README.md)
**← Previous:** [Agent control plane (design review)](../architecture/agent-control-plane.md) · **Next:** [Security baseline](security-baseline.md) →


**Current focus:** `SDBX`, `DEV`, `PROD`  
**Documented for later:** `UAT`, `INTG`

Set `EDIM_ENV` to one of: `sdbx` | `dev` | `uat` | `intg` | `prod`.

---

## `EDIM_ENV` vs deploy configuration

One **deployed App / process** = one **`EDIM_ENV`**. That value is **identity and tagging**, not a substitute for CI/CD env vars.

| Layer | What it does | Example |
|-------|----------------|---------|
| **`EDIM_ENV`** | Tags traces (`env:dev`), fail-closed workspace catalog filter, docs matrix row | `dev` |
| **Deploy env vars** | Primary runtime config: Databricks host/path, table FQNs, Foundry, LangSmith key | `DATABRICKS_HOST`, `LANGCHAIN_PROJECT` |
| **`config/workspaces.yaml`** | **Optional** overlay when one env has **multiple** Databricks workspaces | Leave `workspaces: {}` until needed — see [workspace resolver](../domain/workspace-resolver.md) |
| **`LANGCHAIN_PROJECT`** | LangSmith **tracing project** (Runs tab) | `edim-dde-dev` — not the same string as `EDIM_ENV` |

**R1 default:** one API App per environment; process-level `DATABRICKS_*` only; empty workspace catalog. Add `workspaces.yaml` entries only when DEV (or another env) must route SQL to more than one warehouse/UC target inside the same `EDIM_ENV`.

**Identities (who authenticates):** Identity **U** = signed-in user (SQL on Apps); **A** = host runtime (Key Vault); **B** = Foundry workload SP (`EDIM_FOUNDRY_*`). Full matrix: [Access & permissions](access-and-permissions.md) · [Authentication flows](authentication-flows.md).

---

## Matrix (current)

| Concern | SDBX | DEV | PROD |
|---------|------|-----|------|
| Purpose | Spikes, LangSmith learning | Active development | Live Apps traffic |
| `EDIM_ENV` | `sdbx` | `dev` | `prod` |
| Databricks workspace | Sandbox | One or more DEV workspaces (`dev_1` / …) | Production |
| SQL tables | Sample / synthetic UC | DEV UC FQNs (per workspace via resolver) | Prod UC FQNs |
| Azure OpenAI deployment | Non-prod | DEV deployment | Prod deployment |
| Key Vault (convention) | `edim-dde-sdbx-kv` | `edim-dde-dev-kv` | `edim-dde-prod-kv` |
| LangSmith project | `edim-dde-sdbx` | `edim-dde-dev` | `edim-dde-prod` |
| State store (typical) | `postgres` or `memory` | `postgres` | **`cosmos`** |
| Retrieval (typical) | `faiss` or `memory` | `faiss` / Azure | **`azure_ai_search`** |
| Tracing verbosity | High OK | On | On + PII redaction |
| Agent YAML changes | Experimental OK | Feature branches | Approved versions only |
| Foundry auth | `az login` or SP | SP or `az login` | **`EDIM_FOUNDRY_*` from Key Vault** |
| Typical **host** (runtime) | Local / SDBX Apps | Local or DEV Apps | **Databricks Apps** (ACA optional) |
| Databricks App name (API) | `edim-dde-api-sdbx` (optional) | **`edim-dde-api-dev`** | `edim-dde-api-prod` |

Hosting & identity: [Deploy & hosting](../api/deploy-and-hosting.md) §5 (naming + packaging) · [Access & permissions](access-and-permissions.md) · [Key Vault bootstrap](key-vault-bootstrap.md).  
Agent packing / one vs many apps: [Agent deployment & composition](../architecture/agent-deployment-and-composition.md).

---

## Deferred environments

| Env | Purpose (later) |
|-----|-----------------|
| **UAT** | Business acceptance before PROD |
| **INTG** | Cross-system integration tests |

Do not invent ad-hoc env names. Extend this matrix when UAT/INTG are stood up.

---

## Promotion path (simplified)

```text
SDBX  →  DEV  →  PROD
                 (UAT / INTG inserted later)
```

Promotion checklist (manual for now):

1. YAML validates (`edim-dde-ai` schema)
2. Unit / e2e tests green
3. LangSmith spot-check of a successful run
4. Secrets present in target Key Vault
5. Table FQNs and Foundry deployment confirmed for target env

**Hosting:** first cut = **Databricks Apps**; portable Docker image for Azure Container Apps — see [Deploy & hosting](../api/deploy-and-hosting.md).

---

## Required env vars by environment

See [Environment variables](../reference/env-vars.md) and [.env.example — see domain package `.env.example`.

Minimum for agent invoke:

- Databricks: `DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH`, table FQNs
  (or within-env [workspace catalog](../domain/workspace-resolver.md))
- Foundry: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`
- LangSmith (recommended): `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`
- State store (recommended local): `EDIM_STATE_STORE=postgres` + `EDIM_DATABASE_URL` — see [state-store.md](state-store.md)
- Retrieval (optional local): `EDIM_RETRIEVAL=faiss` + `EDIM_FAISS_INDEX_PATH` — see [retrieval-and-rag.md](retrieval-and-rag.md)
- Platform: `EDIM_ENV`, optional `AZURE_KEY_VAULT_URL` + secret name mappings

<!-- edim-learning-nav -->
---

← [Agent control plane (design review)](../architecture/agent-control-plane.md) · [Guide home](../README.md) · [Security baseline](security-baseline.md) →
