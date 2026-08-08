# Access & permissions (identities, Key Vault, Apps)

**Learning path:** C2b · [Guide home](../README.md)  
**← Previous:** [Security baseline](security-baseline.md) · **Next:** [PII guardrails](pii-guardrails.md) →

This page explains **who authenticates to what** in EDIM DDE — especially on **Databricks Apps**, how that relates to **Azure Key Vault**, and how that differs from notebook `dbutils.secrets`.

---

## 1. The core idea: three identities (do not mix them)

EDIM uses up to **three different identities** in production. Each has one job.

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Identity U — USER (person using the App)                                 │
│   SQL warehouse / UC reads on behalf of the signed-in user               │
│   Via: X-Forwarded-Access-Token → API middleware → Databricks SQL        │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ Identity A — APP RUNTIME (Databricks App service principal)              │
│   “Who is this App process?”                                             │
│   Opens Key Vault (optional) · Databricks resource bindings              │
│   Via: DATABRICKS_CLIENT_ID / DATABRICKS_CLIENT_SECRET (injected by Apps) │
│   Find it: Apps → your app → Authorization tab                           │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ Identity B — FOUNDRY WORKLOAD SP (your Entra app registration)           │
│   “Who calls Azure AI Foundry / OpenAI?”                                 │
│   Via: AZURE_TENANT_ID + AZURE_CLIENT_ID + AZURE_CLIENT_SECRET            │
│   Those values often live *inside* Key Vault as secrets                  │
└──────────────────────────────────────────────────────────────────────────┘
```

| Identity | Typical name in your org | Used for | Where credentials live |
|----------|--------------------------|----------|-------------------------|
| **U** User | Your AAD user | Databricks SQL (Apps) | Forwarded access token (not in KV) |
| **A** App SP | Auto-created per Databricks App | Read KV; Databricks app resources | Injected by Apps as `DATABRICKS_CLIENT_*` |
| **B** Foundry SP | The Entra SP **you** created | Azure AI Foundry chat | Secret values in KV → loaded into `AZURE_*` |

**Your recent work** (create Entra SP, store client id/secret in KV for Foundry) = **Identity B only**. That does **not** replace Identity A or U.

---

## 2. End-to-end flow (Databricks Apps + Key Vault)

```text
  Browser / caller
        │  (user session)
        ▼
  Databricks Apps gateway
        │  attaches X-Forwarded-Access-Token   ← Identity U
        ▼
  edim-dde-api (uvicorn)
        │
        ├─ lifespan: load_key_vault_secrets()
        │     │
        │     │  auth to vault with Identity A
        │     │  (DATABRICKS_CLIENT_ID + SECRET + AZURE_TENANT_ID)
        │     ▼
        │  Azure Key Vault
        │     secrets: azure-client-id, azure-client-secret, azure-tenant-id, …
        │     │
        │     └─► os.environ AZURE_CLIENT_ID / SECRET / TENANT   ← Identity B
        │
        ├─ POST /api/v1/recommendations
        │     ├─ domain.sql.query  → warehouse with Identity U token
        │     └─ llm_chain         → Foundry with Identity B (ClientSecretCredential)
        │
        └─ /health (no secrets required)
```

Notebook comparison:

| Notebook | Databricks Apps / API |
|----------|------------------------|
| `dbutils.secrets.get(scope, key)` | **Not available** — Apps is a normal Python process |
| Secret scope (often KV-backed) | Direct **Key Vault SDK** (`SecretClient`) or Apps env secrets |
| Cluster / job identity | App SP (**A**) + user token (**U**) + Foundry SP (**B**) |

Same Key Vault can back both worlds; the **client** differs (`dbutils` vs our SDK bootstrap).

---

## 3. Where to find the App’s identity (Identity A)

1. Databricks workspace → **Apps** → open your app.  
2. Open the **Authorization** tab.  
3. Copy the app’s **service principal** application (client) id.  

Databricks creates this SP when the app is created. It stays stable across redeploys; deleting the app deletes the SP.

Official docs: [Configure authorization in a Databricks app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth).

At runtime Apps injects (names may vary slightly by cloud/docs version):

| Env var | Meaning |
|---------|---------|
| `DATABRICKS_CLIENT_ID` | App SP client id (Identity A) |
| `DATABRICKS_CLIENT_SECRET` | App SP secret |

You also set **`AZURE_TENANT_ID`** (directory / tenant GUID — not secret) so the API can use client-credentials against Azure AD for Key Vault.

---

## 4. Grant Identity A permission to read Key Vault

Only required if the App will call Key Vault at startup (`AZURE_KEY_VAULT_URL` set).

### 4.1 Portal steps

1. Azure Portal → your **Key Vault**.  
2. Confirm permission model is **Azure role-based access control** (recommended).  
3. **Access control (IAM)** → **Add role assignment**.  
4. Role: **Key Vault Secrets User** (get/list secrets).  
5. Members: find the **App service principal** from §3 (search by name or application id).  
6. Review + assign. Wait a few minutes for RBAC propagation.

### 4.2 What Identity B needs (separate)

On the **Foundry / Azure OpenAI** resource (not the vault):

1. IAM → grant your **Foundry SP** (Identity B) a role that can call the deployment  
   (e.g. **Cognitive Services OpenAI User** or your org’s equivalent).  
2. Store that SP’s client id, secret, and tenant as vault secrets (names below).

Identity A only needs vault **read**. Identity B needs Foundry **invoke**.

---

## 5. How EDIM loads secrets (runtime)

Code: `edim_dde_domain.security.keyvault.load_key_vault_secrets`  
Called from API lifespan when `AZURE_KEY_VAULT_URL` is set.

### 5.1 Which credential opens the vault?

| Priority | Condition | Credential |
|----------|-----------|------------|
| 1 | `EDIM_KV_CLIENT_ID` + `EDIM_KV_CLIENT_SECRET` + tenant | Explicit vault-reader SP |
| 2 | `DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET` + `AZURE_TENANT_ID` | **Apps SP (Identity A)** |
| 3 | Else | `DefaultAzureCredential` (local `az login`, ACA managed identity, …) |

This avoids using `AZURE_CLIENT_*` to open the vault, so those names stay free for **Foundry (Identity B)** values loaded from secrets.

### 5.2 Default secret name → env map

| Key Vault secret name | Written to env |
|-----------------------|----------------|
| `azure-client-id` | `AZURE_CLIENT_ID` |
| `azure-client-secret` | `AZURE_CLIENT_SECRET` |
| `azure-tenant-id` | `AZURE_TENANT_ID` |
| `langchain-api-key` | `LANGCHAIN_API_KEY` |

Override: `EDIM_KV_SECRET_MAP=vault-name:ENV_VAR,...`

### 5.3 Overwrite rules

- If an env var is **already set**, KV does **not** overwrite it (so laptop `.env` wins).  
- Set `EDIM_KV_FORCE=1` to overwrite (use carefully).

Install: `pip install 'edim-dde-domain[azure,keyvault]'`.

---

## 6. Recommended setups

### 6.1 Databricks Apps — Key Vault fetch (full Option B)

```text
App env (non-secret):
  AZURE_KEY_VAULT_URL=https://your-vault.vault.azure.net/
  AZURE_TENANT_ID=<directory-guid>          # for Apps SP → AAD
  AZURE_OPENAI_ENDPOINT=...
  AZURE_OPENAI_DEPLOYMENT_NAME=...
  DATABRICKS_HOST / HTTP_PATH / table FQNs
  # DATABRICKS_CLIENT_* injected by platform

Vault secrets (Identity B):
  azure-client-id, azure-client-secret, azure-tenant-id (± langchain-api-key)

Azure IAM:
  App SP (A) → Key Vault Secrets User on vault
  Foundry SP (B) → OpenAI / Foundry data-plane role
```

Do **not** put Foundry client secret in `app.yaml`.

### 6.2 Databricks Apps — inject Foundry SP via Apps secrets (simpler first cut)

```text
App env / secrets UI:
  AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET   ← Identity B
  AZURE_OPENAI_* , DATABRICKS_* table settings

Leave AZURE_KEY_VAULT_URL unset → skip SDK bootstrap.
Still store the same values in KV as the human source of truth if you want.
```

### 6.3 Local laptop

```text
az login
# Optional: AZURE_KEY_VAULT_URL + DefaultAzureCredential reads vault
# Or put AZURE_CLIENT_* in .env for Foundry without KV
```

SQL + Foundry both use `az login` when SP env is empty.

### 6.4 Azure Container Apps

Prefer **managed identity** as Identity A (`DefaultAzureCredential`) → KV → Foundry `AZURE_*`.  
Grant the ACA MI **Key Vault Secrets User**; Foundry SP remains Identity B in the vault.

---

## 7. Permissions checklist (copy/paste)

**Azure Key Vault**

- [ ] Vault URI known → `AZURE_KEY_VAULT_URL`  
- [ ] Secrets created with expected names (or `EDIM_KV_SECRET_MAP`)  
- [ ] Identity A (App SP or ACA MI) has **Key Vault Secrets User**  
- [ ] Network: App can reach vault (public / private endpoint / firewall allow)

**Foundry / Azure OpenAI**

- [ ] Identity B SP created in Entra  
- [ ] Identity B granted invoke role on the Foundry/OpenAI resource  
- [ ] Deployment name matches `AZURE_OPENAI_DEPLOYMENT_NAME`  
- [ ] Client id/secret stored in vault (or Apps secrets)

**Databricks**

- [ ] App created; Authorization tab SP noted  
- [ ] Users who call the App can use the warehouse / UC tables (Identity U)  
- [ ] App resource bindings (warehouse) as required by your workspace  

**API config**

- [ ] `AZURE_TENANT_ID` set when using Apps SP → KV  
- [ ] `EDIM_STRICT_STARTUP` optional for fail-fast  

---

## 8. Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| KV skipped in logs | `AZURE_KEY_VAULT_URL` unset |
| 403 from Key Vault | App SP (A) missing **Secrets User**; wrong tenant; firewall |
| Warning: Apps SP present but no tenant | Set `AZURE_TENANT_ID` |
| Foundry 503 after KV load | Identity B missing Foundry role; wrong secret names; empty secret |
| Foundry still using wrong SP | `AZURE_CLIENT_*` already set (`.env` / Apps) and `EDIM_KV_FORCE` not set |
| SQL works locally, fails on Apps | Local used `az login`; Apps needs **user** forwarded token (U), not Foundry SP |
| Expecting `dbutils` on Apps | Not available — use KV SDK or Apps secrets |

---

## 9. Related docs

| Doc | Topic |
|-----|--------|
| [Security baseline](security-baseline.md) | Role matrix (app roles, Phase 0 docs-only) |
| [Auth and SQL](../architecture/auth-and-sql.md) | User token vs `az login` for warehouse |
| [Deploy & hosting](../api/deploy-and-hosting.md) | Apps / Docker packaging |
| [Env vars](../reference/env-vars.md) | Full variable catalog |

<!-- edim-learning-nav -->
---

← [Security baseline](security-baseline.md) · [Guide home](../README.md) · [PII guardrails](pii-guardrails.md) →
