# Key Vault bootstrap

**Learning path:** C2c · [Guide home](../README.md)  
**← Previous:** [Authentication flows](authentication-flows.md) · **Next:** [PII guardrails](pii-guardrails.md) →

**This page covers:** how the API loads secrets from Azure Key Vault at startup — who opens the vault, default secret→env mapping, and `EDIM_KV_SECRET_MAP`.

**Not on this page:**

| Topic | Go to |
|-------|--------|
| Identities U / A / B and host matrix | [Access & permissions](access-and-permissions.md) |
| Visual auth flows (local / Apps / ACA) | [Authentication flows](authentication-flows.md) |
| ACA managed identity warehouse/UC grants | [Deploy & hosting §6.4](../api/deploy-and-hosting.md#64-aca-sql-grant-managed-identity-warehouse-uc) |
| Full env catalog | [Environment variables](../reference/env-vars.md) |

Code: `edim_dde_domain.security.keyvault.load_key_vault_secrets`  
Runs in API lifespan when `AZURE_KEY_VAULT_URL` is set.  
Install: `pip install 'edim-dde-domain[azure,keyvault]'`.

---

## 1. Who opens the vault (Identity A)

| Priority | When | Typical host |
|----------|------|--------------|
| 1 | `EDIM_KV_CLIENT_ID` + `EDIM_KV_CLIENT_SECRET` + tenant | Explicit vault-reader SP |
| 2 | `DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET` + `AZURE_TENANT_ID` | **Databricks Apps** |
| 3 | `DefaultAzureCredential` | **Local** (`az login`), **ACA MI** |

`AZURE_TENANT_ID` here is the **directory GUID** for Apps SP client-credentials — not the Foundry SP.

Secrets loaded from the vault are usually **Identity B** (`EDIM_FOUNDRY_*`) and optional keys such as `LANGCHAIN_API_KEY`. Identity B also needs a Foundry/OpenAI data-plane role on the model resource.

---

## 2. What is `EDIM_KV_SECRET_MAP`?

Maps **process environment variable names** ← **Key Vault secret names** at API startup  
(“what the app needs” → “which vault secret”).

| Without `EDIM_KV_SECRET_MAP` | With `EDIM_KV_SECRET_MAP` |
|------------------------------|---------------------------|
| Code uses the **default** map (§3) | You choose which env vars are filled from which vault secrets |

**Format** (comma-separated pairs):

```text
ENV_VAR_NAME:vaultSecretName,OTHER_ENV:otherSecret
```

Common mistake to avoid:

```text
vaultSecretName:ENV_VAR_NAME   # wrong
```

**Rules:**

- Only applies when `AZURE_KEY_VAULT_URL` is set (otherwise bootstrap is skipped).
- Existing env values are **not** overwritten unless `EDIM_KV_FORCE=1`.
- Vault secret **names** are whatever you created in the vault.
- Env names must match what EDIM reads (`EDIM_FOUNDRY_*`, `LANGCHAIN_API_KEY`, …).
- Pair direction is always `ENV_VAR_NAME:vaultSecretName`.

---

## 3. Default map

Used when `EDIM_KV_SECRET_MAP` is **unset**:

| Env var set | Vault secret name |
|-------------|-------------------|
| `EDIM_FOUNDRY_CLIENT_ID` | `azure-client-id` |
| `EDIM_FOUNDRY_CLIENT_SECRET` | `azure-client-secret` |
| `EDIM_FOUNDRY_TENANT_ID` | `azure-tenant-id` |
| `LANGCHAIN_API_KEY` | `langchain-api-key` |

Foundry goes to `EDIM_FOUNDRY_*` (not `AZURE_CLIENT_*`) so SQL’s `DefaultAzureCredential` is not tied to the Foundry SP.

---

## 4. Examples

### Use defaults (leave map unset)

```text
AZURE_KEY_VAULT_URL=https://edim-dde-dev-kv.vault.azure.net/
# EDIM_KV_SECRET_MAP unset → default map in §3
```

Create vault secrets named `azure-client-id`, `azure-client-secret`, `azure-tenant-id` with Foundry SP values.

### Custom vault secret names

```text
EDIM_KV_SECRET_MAP=EDIM_FOUNDRY_CLIENT_ID:foundry-client-id,EDIM_FOUNDRY_CLIENT_SECRET:foundry-client-secret,EDIM_FOUNDRY_TENANT_ID:foundry-tenant-id,LANGCHAIN_API_KEY:langsmith-key
```

### Also load Cosmos / Search keys later

```text
EDIM_KV_SECRET_MAP=EDIM_FOUNDRY_CLIENT_ID:azure-client-id,EDIM_FOUNDRY_CLIENT_SECRET:azure-client-secret,EDIM_FOUNDRY_TENANT_ID:azure-tenant-id,EDIM_COSMOS_KEY:cosmos-key,EDIM_AZURE_SEARCH_KEY:search-key
```

### Force overwrite of already-set env

```text
EDIM_KV_FORCE=1
```

---

## 5. Related env vars (summary)

| Variable | Purpose |
|----------|---------|
| `AZURE_KEY_VAULT_URL` | Vault URI; unset = skip bootstrap |
| `EDIM_KV_SECRET_MAP` | Optional `ENV:vaultSecret` map (§2–§4) |
| `EDIM_KV_FORCE` | `1` = overwrite existing env |
| `EDIM_KV_CLIENT_*` | Optional dedicated vault-reader SP |
| `DATABRICKS_CLIENT_*` + `AZURE_TENANT_ID` | Apps SP opens vault |
| `EDIM_FOUNDRY_*` | Target env for Foundry SP (Identity B) |

Full catalog: [Environment variables](../reference/env-vars.md).

---

## 6. Troubleshooting (Key Vault)

| Symptom | Likely cause |
|---------|----------------|
| KV skipped | `AZURE_KEY_VAULT_URL` unset |
| 403 Key Vault | **App SP** missing **Key Vault Secrets User** (§7); wrong tenant; vault firewall |
| Apps SP warning in logs | Set `AZURE_TENANT_ID` (directory GUID) in `app.yaml` |
| Wrong env after load | Check `EDIM_KV_SECRET_MAP` pairs; secret names in vault |
| SQL works, Foundry fails with `DefaultAzureCredential failed… EnvironmentCredential…` | **Identity B not loaded** — KV bootstrap failed or secrets missing. App SP must open vault (§7); map must set `EDIM_FOUNDRY_CLIENT_ID` + `EDIM_FOUNDRY_CLIENT_SECRET`. Not an SSO / SQL-scope issue. |
| Foundry still missing after grant | Secret names wrong; wait for RBAC propagation; restart App; check logs (§7.5) |

---

## 7. Grant Databricks App SP → Key Vault Secrets User

Required when the App opens the vault with injected `DATABRICKS_CLIENT_ID` / `SECRET` (**Identity A**).

Do **not** confuse these three:

| Name | What it is | Used for |
|------|------------|----------|
| **App SP** (Identity A) | Databricks-created service principal **for this App** | Open Key Vault at startup |
| **Foundry SP** (Identity B) | Separate Entra app whose id/secret live **in** the vault → `EDIM_FOUNDRY_*` | Call Azure AI Foundry / OpenAI |
| **Signed-in user** (Identity U) | Person using Swagger / the App | Databricks SQL via `X-Forwarded-Access-Token` |

SQL can succeed while Foundry fails if A cannot read B’s secrets from the vault.

### 7.1 Where to find the App SP (Databricks UI)

1. Sign into the **Databricks workspace** that hosts the App.  
2. Left nav (or app switcher) → **Compute** → **Apps**, or workspace **Apps**.  
3. Open your API app (e.g. **`edim-dde-api-dev`**).  
4. Open the **Authorization** tab  
   (UI labels vary: **Authorization**, **Permissions**, or **Service principal**).  
5. Find the **App service principal** / **OAuth** client for **this app** (not a warehouse user, not the Foundry SP).  
6. Copy the **Application (client) ID** (GUID).  
   - This is the value Azure IAM needs as the assignee.  
   - Databricks also injects the same id into the running App as `DATABRICKS_CLIENT_ID` (secret is `DATABRICKS_CLIENT_SECRET` — do not put those in git).

**CLI alternative** (after `databricks auth login`):

```bash
databricks apps get edim-dde-api-dev
# Look for the app’s service principal / client id in the JSON
# (field names vary by CLI version — search for client_id / service_principal)
```

Official: [Configure authorization in a Databricks app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth).

### 7.2 Portal — assign Key Vault Secrets User

1. Azure Portal → **Key Vault** used by the App  
   (from `AZURE_KEY_VAULT_URL`, e.g. `dlabs-dev-eus-app-a-kv`).  
2. **Access control (IAM)** → **Add** → **Add role assignment**.  
3. Role: **Key Vault Secrets User**.  
4. **Members** → **+ Select members** → paste the **Application (client) ID** from §7.1  
   (or search the SP display name).  
5. **Review + assign**.  
6. If the vault still uses **access policies** (legacy) instead of RBAC: add a policy for that SP with **Get** + **List** on secrets (prefer RBAC on new vaults).

Also ensure network rules allow the App’s egress (public allowlist / private endpoint as required).

RBAC can take a few minutes to propagate; then **restart or redeploy** the App.

### 7.3 Azure CLI

```bash
# Values you fill in
VAULT_NAME=dlabs-dev-eus-app-a-kv   # or your vault name
APP_SP_CLIENT_ID=<application-client-id-from-§7.1>

VAULT_ID=$(az keyvault show --name "$VAULT_NAME" --query id -o tsv)

az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee "$APP_SP_CLIENT_ID" \
  --scope "$VAULT_ID"
```

If assignee lookup fails, resolve object id first:

```bash
SP_OBJECT_ID=$(az ad sp show --id "$APP_SP_CLIENT_ID" --query id -o tsv)
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee-object-id "$SP_OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --scope "$VAULT_ID"
```

### 7.4 Secrets the App must be able to read

With current `deploy/databricks-app/app.yaml` style map:

```text
EDIM_KV_SECRET_MAP=EDIM_FOUNDRY_CLIENT_ID:DLABS-DIM-ADB-APP-AIF-APPID,EDIM_FOUNDRY_CLIENT_SECRET:DLABS-DIM-ADB-APP-AIF-APPKEY
```

Those **vault secret names** (right side) must exist. Tenant often comes from `AZURE_TENANT_ID` in `app.yaml` (shared directory GUID), or add `EDIM_FOUNDRY_TENANT_ID:<vault-secret>`.

### 7.5 Verify (logs + behavior)

Redeploy or **Start** the App with `AZURE_KEY_VAULT_URL` + `AZURE_TENANT_ID` set. In App logs look for:

| Log / behavior | Meaning |
|----------------|---------|
| `Key Vault auth via DATABRICKS_CLIENT_* (Apps SP) → https://…vault.azure.net/` | Identity A opened the vault |
| `Loaded Key Vault secret … → env EDIM_FOUNDRY_CLIENT_ID` (and `…_SECRET`) | Identity B env ready |
| `Key Vault bootstrap skipped/failed: …` or 403 | Fix §7.2 grant / secret names / network |
| Foundry still `DefaultAzureCredential failed…` | `EDIM_FOUNDRY_CLIENT_*` still unset — secrets not loaded |

**Quick prove-out without KV:** Apps → Environment / secrets → set `EDIM_FOUNDRY_CLIENT_ID`, `EDIM_FOUNDRY_CLIENT_SECRET`, `EDIM_FOUNDRY_TENANT_ID` directly; temporarily unset `AZURE_KEY_VAULT_URL` if you only want to validate Foundry.

Full Apps create/deploy: [Deploy & hosting §5](../api/deploy-and-hosting.md#5-deploy-databricks-apps-default).

<!-- edim-learning-nav -->
---

← [Authentication flows](authentication-flows.md) · [Guide home](../README.md) · [PII guardrails](pii-guardrails.md) →
