# Key Vault bootstrap

**Learning path:** C2c · [Guide home](../README.md)  
**← Previous:** [Access & permissions](access-and-permissions.md) · **Next:** [PII guardrails](pii-guardrails.md) →

**This page covers:** how the API loads secrets from Azure Key Vault at startup — who opens the vault, default secret→env mapping, and `EDIM_KV_SECRET_MAP`.

**Not on this page:**

| Topic | Go to |
|-------|--------|
| Identities U / A / B and host matrix | [Access & permissions](access-and-permissions.md) |
| ACA managed identity warehouse/UC grants | [Deploy & hosting §6.3](../api/deploy-and-hosting.md#63-aca-sql--grant-managed-identity-warehouse--uc) |
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

Maps **Key Vault secret names** → **process environment variable names** at API startup.

| Without `EDIM_KV_SECRET_MAP` | With `EDIM_KV_SECRET_MAP` |
|------------------------------|---------------------------|
| Code uses the **default** map (§3) | You choose which vault secrets land in which env vars |

**Format** (comma-separated pairs):

```text
vaultSecretName:ENV_VAR_NAME,otherSecret:OTHER_ENV
```

**Rules:**

- Only applies when `AZURE_KEY_VAULT_URL` is set (otherwise bootstrap is skipped).
- Existing env values are **not** overwritten unless `EDIM_KV_FORCE=1`.
- Vault secret **names** are whatever you created in the vault.
- Env names must match what EDIM reads (`EDIM_FOUNDRY_*`, `LANGCHAIN_API_KEY`, …).

---

## 3. Default map

Used when `EDIM_KV_SECRET_MAP` is **unset**:

| Vault secret name | Env var set |
|-------------------|-------------|
| `azure-client-id` | `EDIM_FOUNDRY_CLIENT_ID` |
| `azure-client-secret` | `EDIM_FOUNDRY_CLIENT_SECRET` |
| `azure-tenant-id` | `EDIM_FOUNDRY_TENANT_ID` |
| `langchain-api-key` | `LANGCHAIN_API_KEY` |

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
EDIM_KV_SECRET_MAP=foundry-client-id:EDIM_FOUNDRY_CLIENT_ID,foundry-client-secret:EDIM_FOUNDRY_CLIENT_SECRET,foundry-tenant-id:EDIM_FOUNDRY_TENANT_ID,langsmith-key:LANGCHAIN_API_KEY
```

### Also load Cosmos / Search keys later

```text
EDIM_KV_SECRET_MAP=azure-client-id:EDIM_FOUNDRY_CLIENT_ID,azure-client-secret:EDIM_FOUNDRY_CLIENT_SECRET,azure-tenant-id:EDIM_FOUNDRY_TENANT_ID,cosmos-key:EDIM_COSMOS_KEY,search-key:EDIM_AZURE_SEARCH_KEY
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
| `EDIM_KV_SECRET_MAP` | Optional secret→env map (§2–§4) |
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
| 403 Key Vault | Identity A missing **Key Vault Secrets User**; tenant; firewall |
| Apps SP warning | Set `AZURE_TENANT_ID` |
| Wrong env after load | Check `EDIM_KV_SECRET_MAP` pairs; secret names in vault |
| Foundry still missing | Secret not in map / not created / `EDIM_KV_FORCE` needed |

---

## 7. Grant Databricks App SP → Key Vault Secrets User

Required when the App opens the vault with injected `DATABRICKS_CLIENT_ID` / `SECRET` (Identity A).

### 7.1 Find the App service principal

1. Databricks workspace → **Apps** → open **`edim-dde-api-dev`** (or your API app name).  
2. Open **Authorization** (sometimes labeled permissions / service principal).  
3. Copy the Entra **Application (client) ID** of the app’s service principal.  
   (Also available after `databricks apps create` — confirm in UI.)

Official: [Configure authorization in a Databricks app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth).

### 7.2 Portal (DEV vault)

1. Azure Portal → **Key Vault** (e.g. `edim-dde-dev-kv`).  
2. **Access control (IAM)** → **Add role assignment**.  
3. Role: **Key Vault Secrets User**.  
4. Members: find the App SP by application (client) ID or display name → **Review + assign**.  
5. If the vault uses **access policies** (legacy) instead of RBAC: add a policy for that SP with **Get** + **List** on secrets (prefer RBAC on new vaults).

Also ensure network rules allow the App’s egress (public allowlist / private endpoint as required).

### 7.3 Azure CLI

```bash
# Values you fill in
VAULT_NAME=edim-dde-dev-kv
APP_SP_CLIENT_ID=<application-client-id-from-apps-authorization>

# Resolve vault resource id
VAULT_ID=$(az keyvault show --name "$VAULT_NAME" --query id -o tsv)

# Assign RBAC role (assignee = app id or object id — CLI accepts both in most tenants)
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

### 7.4 Verify

Redeploy or restart the App with `AZURE_KEY_VAULT_URL` + `AZURE_TENANT_ID` set. Logs should show Key Vault auth via `DATABRICKS_CLIENT_* (Apps SP)` and loaded `EDIM_FOUNDRY_*` (no 403).

Full Apps create/deploy: [Deploy & hosting §5](../api/deploy-and-hosting.md#5-deploy--databricks-apps-default).

<!-- edim-learning-nav -->
---

← [Access & permissions](access-and-permissions.md) · [Guide home](../README.md) · [PII guardrails](pii-guardrails.md) →
