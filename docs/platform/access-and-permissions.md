# Access & permissions (identities by host)

**Learning path:** C2b · [Guide home](../README.md)  
**← Previous:** [Security baseline](security-baseline.md) · **Next:** [Key Vault bootstrap](key-vault-bootstrap.md) →

**This page covers:** who is Identity **U / A / B**, and which identity runs SQL vs Foundry vs Key Vault on each host.

**Not on this page** (follow the links):

| Topic | Go to |
|-------|--------|
| Key Vault load order, `EDIM_KV_SECRET_MAP`, examples | [Key Vault bootstrap](key-vault-bootstrap.md) |
| Packaging Apps / Docker / ACA | [Deploy & hosting](../api/deploy-and-hosting.md) |
| Step-by-step: grant ACA MI warehouse + UC | [Deploy & hosting — ACA SQL MI](../api/deploy-and-hosting.md#63-aca-sql--grant-managed-identity-warehouse--uc) |
| Token resolution code paths | [Auth and SQL](../architecture/auth-and-sql.md) |
| Env var catalog | [Environment variables](../reference/env-vars.md) |

**No separate code forks per host** — one API process; behavior follows env + credential resolution.

---

## 1. Three identities (do not mix them)

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Identity U — USER                                                        │
│   SQL as the signed-in person (Databricks Apps)                          │
│   Via: X-Forwarded-Access-Token → middleware → warehouse                 │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ Identity A — HOST RUNTIME (“who is this process?”)                       │
│   Opens Key Vault; may call Azure as the platform identity               │
│   Manifests as:                                                          │
│     • Databricks Apps → app SP (DATABRICKS_CLIENT_ID / SECRET)           │
│     • Azure Container Apps → managed identity (DefaultAzureCredential)   │
│     • Local laptop → az login (DefaultAzureCredential)                   │
│     • Optional → EDIM_KV_CLIENT_* dedicated vault-reader SP              │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ Identity B — FOUNDRY WORKLOAD SP (Entra app you create)                  │
│   Calls Azure AI Foundry / OpenAI                                        │
│   Via: EDIM_FOUNDRY_TENANT_ID + EDIM_FOUNDRY_CLIENT_ID +                 │
│        EDIM_FOUNDRY_CLIENT_SECRET                                        │
│   Often stored in Key Vault, loaded at API startup                       │
│   Never put Foundry SP in AZURE_CLIENT_* (pollutes SQL DAC)              │
└──────────────────────────────────────────────────────────────────────────┘
```

| Identity | Used for | Databricks Apps | ACA / Docker | Local machine |
|----------|----------|-----------------|--------------|---------------|
| **U** | SQL as end user | Forwarded access token | Usually **absent** | N/A (`az login` is you) |
| **A** | Open KV / platform Azure | App SP (`DATABRICKS_CLIENT_*`) | Container **managed identity** | `az login` |
| **B** | Foundry LLM | Secrets → `EDIM_FOUNDRY_*` | Same (KV or ACA secret refs) | `az login` or `.env` SP |

Creating an Entra SP and storing its client id/secret in KV for Foundry = **Identity B only**.

---

## 2. Host comparison matrix

| Host | How you run | SQL warehouse auth | Foundry auth | Who opens Key Vault | Deploy artifact |
|------|-------------|--------------------|--------------|---------------------|-----------------|
| **Local machine** | `uvicorn` / IDE | `az login` → `DefaultAzureCredential` | `az login` if `EDIM_FOUNDRY_*` empty; else SP | Optional: `DefaultAzureCredential` | Editable installs |
| **Databricks Apps** | `app.yaml` + Apps runtime | **Identity U** (`X-Forwarded-Access-Token`) | **Identity B** from KV or Apps secrets | **Identity A** = App SP | `deploy/databricks-app/` |
| **Docker (local/CI)** | `deploy/docker/Dockerfile` | Same as local or MI | SP via `EDIM_FOUNDRY_*` / KV | Inject secrets or host `az login` | Same image as ACA |
| **Azure Container Apps** | Same Docker image | **Identity A** = container MI | Identity B → `EDIM_FOUNDRY_*` | **Identity A** = ACA MI | ACR + ACA env |
| **AKS / App Service** (later) | Same image / startup CMD | Same pattern as ACA | Same | Workload MI | Same env contract |

**Why `EDIM_FOUNDRY_*`:** SQL’s `DefaultAzureCredential` auto-reads `AZURE_CLIENT_*`. Foundry must use dedicated names so ACA SQL stays on the **MI**, not the Foundry SP. Details: [Key Vault bootstrap](key-vault-bootstrap.md).

---

## 3. End-to-end flows by host

### 3.1 Databricks Apps + Key Vault

```text
  User → Apps gateway → X-Forwarded-Access-Token (U)
                      → edim-dde-api
                           ├─ KV auth = DATABRICKS_CLIENT_* (A) → EDIM_FOUNDRY_* (B)
                           ├─ SQL → U
                           └─ LLM → B
```

### 3.2 Local machine

```text
  az login → uvicorn
               ├─ optional KV via DefaultAzureCredential
               ├─ SQL → az login
               └─ LLM → az login or EDIM_FOUNDRY_* from .env / KV
```

### 3.3 Azure Container Apps

```text
  Caller → ACA (Docker image, MI = A)
               ├─ KV via MI → EDIM_FOUNDRY_* (B)
               ├─ SQL → MI (A)
               └─ LLM → B
```

How to grant the MI warehouse + UC: [Deploy & hosting §6.3](../api/deploy-and-hosting.md#63-aca-sql--grant-managed-identity-warehouse--uc).

### 3.4 Notebook `dbutils` (not Apps)

`dbutils.secrets.get` works only in Databricks notebooks/jobs. Apps/API use Key Vault SDK or host secret injection.

---

## 4. Where to find Identity A

| Host | Where to look | Grant on Key Vault |
|------|---------------|--------------------|
| **Databricks Apps** | Apps → app → **Authorization** → service principal | That SP → **Key Vault Secrets User** ([step-by-step](key-vault-bootstrap.md#7-grant-databricks-app-sp--key-vault-secrets-user)) |
| **Azure Container Apps** | ACA → Identity → system/user-assigned MI | That MI → **Key Vault Secrets User** |
| **Local** | Your user after `az login` | Your user (or skip KV; use `.env`) |
| **Explicit reader** | Entra app for `EDIM_KV_CLIENT_*` | That SP → **Key Vault Secrets User** |

Apps injects `DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET`. Set **`AZURE_TENANT_ID`** (tenant GUID) so the App SP can open Key Vault via client-credentials.

Apps docs: [Configure authorization in a Databricks app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth).

---

## 5. Permissions checklist

- [ ] Foundry endpoint + deployment  
- [ ] Warehouse host/path + table FQNs (live SQL)  
- [ ] If KV: follow [Key Vault bootstrap](key-vault-bootstrap.md) (URL, secrets, Identity A = Secrets User)  
- [ ] Apps: Authorization SP + tenant; users can query UC  
- [ ] ACA: [grant MI warehouse + UC](../api/deploy-and-hosting.md#63-aca-sql--grant-managed-identity-warehouse--uc)  
- [ ] Local: `az login`  
- [ ] Foundry SP only in `EDIM_FOUNDRY_*`  

---

## 6. Troubleshooting (identity)

| Symptom | Likely cause |
|---------|----------------|
| Foundry 503 | Identity B missing / no Foundry role |
| SQL OK local, fail Apps | Need forwarded **user** token (Identity U) |
| SQL fail ACA | MI not granted warehouse/UC — [§6.3](../api/deploy-and-hosting.md#63-aca-sql--grant-managed-identity-warehouse--uc) |
| KV / map errors | [Key Vault bootstrap](key-vault-bootstrap.md) |
| `dbutils` on Apps | Not available |

---

## 7. Related docs

| Doc | Topic |
|-----|--------|
| [Key Vault bootstrap](key-vault-bootstrap.md) | Vault auth order + `EDIM_KV_SECRET_MAP` |
| [Deploy & hosting](../api/deploy-and-hosting.md) | Apps / Docker / ACA packaging + ACA MI grants |
| [Security baseline](security-baseline.md) | App role matrix |
| [Auth and SQL](../architecture/auth-and-sql.md) | Token resolution |
| [Environments](environments.md) | SDBX / DEV / PROD |
| [Env vars](../reference/env-vars.md) | Catalog |

<!-- edim-learning-nav -->
---

← [Security baseline](security-baseline.md) · [Guide home](../README.md) · [Key Vault bootstrap](key-vault-bootstrap.md) →
