# Access & permissions (C2b)

**Learning path:** C2b · [Preface](../README.md)  
**← Previous:** [Security baseline](security-baseline.md) · **Next:** [Authentication flows](authentication-flows.md) →

## Chapter summary

This chapter defines the three runtime identities — **U** (user), **A** (host),
**B** (Foundry) — and which identity runs **SQL**, **Foundry**, and **Key
Vault** on Local, Databricks Apps, ACA Native, Standalone Agent Server on ACA,
and AKS. Platform engineers use it when wiring ingress authorization, KV
grants, workload identity, or ACA managed identity.

**Outcome:** you can map every credential failure to the correct identity and host without mixing Foundry SP into SQL’s `DefaultAzureCredential` chain.

---

## Prerequisites

| Topic | Chapter |
|-------|---------|
| Trust boundaries / roles | [Security baseline (C2)](security-baseline.md) |
| Token resolution code | [Auth and SQL (B7)](../architecture/auth-and-sql.md) |
| Vault load order | [Key Vault bootstrap (C2c)](key-vault-bootstrap.md) |
| Deployment targets | [Deployment targets and release runbook](../api/deployment-targets.md) |

!!! note "Scope of this page"
    Visual end-to-end auth diagrams: [Authentication flows](authentication-flows.md). ACA MI warehouse grants: [Deploy §6.4](../api/deploy-and-hosting.md#64-aca-sql-grant-managed-identity-warehouse-uc).

**No separate code forks per host** — the shared graph package is reused;
behavior follows the selected host adapter, environment, and credential
resolution.

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

| Identity | Used for | Databricks Apps | ACA Native / Agent Server | Full LangSmith on AKS | Local machine |
|----------|----------|-----------------|--------------------------|-------------------------|--------------|
| **U** | SQL/UI end user | Forwarded access token | Usually **absent**; ingress authenticates the caller | Entra user for UI; service calls use workload identity | `az login` user |
| **A** | Open KV / platform Azure | App SP (`DATABRICKS_CLIENT_*`) | Container managed identity | AKS workload identity | `az login` |
| **B** | Foundry LLM | Secrets → `EDIM_FOUNDRY_*` SP, or API key | Same (KV or ACA secret refs) | Platform-managed secret or workload identity | `az login`, `.env` SP, or API key |

Creating an Entra SP and storing its client id/secret in KV for Foundry = **Identity B only**.

!!! warning "Never put Foundry in AZURE_CLIENT_*"
    SQL’s `DefaultAzureCredential` auto-reads `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET`. Foundry **must** use `EDIM_FOUNDRY_*` so Apps/ACA SQL stay on Identity **U** or **A**, not the Foundry SP.

---

## 2. Host comparison matrix

| Host | How you run | SQL warehouse auth | Foundry auth | Who opens Key Vault | Deploy artifact |
|------|-------------|--------------------|--------------|---------------------|-----------------|
| **Local machine** | `uvicorn` / IDE | `az login` → `DefaultAzureCredential` | SP if set; else API key; else `az login` | Optional: `DefaultAzureCredential` | Editable installs |
| **Databricks Apps** | `app.yaml` + Apps runtime | **Identity U** (`X-Forwarded-Access-Token`) | **Identity B** from KV or Apps secrets | **Identity A** = App SP | `deploy/databricks-app/` |
| **Docker (local/CI)** | `deploy/docker/Dockerfile` | Same as local or MI | SP via `EDIM_FOUNDRY_*` / KV | Inject secrets or host `az login` | Same image as ACA |
| **Azure Container Apps** | Same Docker image | **Identity A** = container MI | Identity B → `EDIM_FOUNDRY_*` | **Identity A** = ACA MI | ACR + ACA env |
| **Standalone Agent Server on ACA** | Agent Server image + graph manifest | **Identity A** = ACA MI | Identity B → `EDIM_FOUNDRY_*` | **Identity A** = ACA MI | Target bundle |
| **Full self-hosted LangSmith on AKS** | Vendor platform + Agent Server bundle | Platform workload identity | Platform secret/workload identity | AKS workload identity | Versioned platform artifact |

**Why `EDIM_FOUNDRY_*`:** SQL’s `DefaultAzureCredential` auto-reads `AZURE_CLIENT_*`. Foundry must use dedicated names so ACA SQL stays on the **MI**, not the Foundry SP. Details: [Key Vault bootstrap](key-vault-bootstrap.md).

---

## 3. End-to-end flows by host

**Full DFD-style diagrams (local · Apps · ACA · per-service matrix):**  
→ **[Authentication flows](authentication-flows.md)**

### 3.1 Databricks Apps + Key Vault (sketch)

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
               └─ LLM → SP, else API key, else az login
```

### 3.3 Azure Container Apps

```text
  Caller → ACA (Docker image, MI = A)
               ├─ KV via MI → EDIM_FOUNDRY_* (B)
               ├─ SQL → MI (A)
               └─ LLM → B
```

How to grant the MI warehouse + UC: [Deploy & hosting §6.4](../api/deploy-and-hosting.md#64-aca-sql-grant-managed-identity-warehouse-uc).

### 3.4 Notebook `dbutils` (not Apps)

`dbutils.secrets.get` works only in Databricks notebooks/jobs. Apps/API use Key Vault SDK or host secret injection.

---

## 4. Where to find Identity A (App SP)

| Host | Where to look | Grant on Key Vault |
|------|---------------|--------------------|
| **Databricks Apps** | **Apps → your app → Authorization** → copy **Application (client) ID** of the **app service principal** | That SP → **Key Vault Secrets User** — full UI + CLI: [Key Vault §7](key-vault-bootstrap.md#7-grant-databricks-app-sp-key-vault-secrets-user) |
| **Azure Container Apps** | ACA → Identity → system/user-assigned MI | That MI → **Key Vault Secrets User** |
| **Local** | Your user after `az login` | Your user (or skip KV; use `.env`) |
| **Explicit reader** | Entra app for `EDIM_KV_CLIENT_*` | That SP → **Key Vault Secrets User** |

**Apps UI path (short):** workspace → **Apps** → **`edim-dde-api-dev`** → **Authorization** → App service principal → **Application (client) ID**.  
That ID is Identity **A** (opens KV). It is **not** the Foundry SP and **not** your user.

Apps injects the same principal as `DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET`. Set **`AZURE_TENANT_ID`** (directory GUID) so the App SP can open Key Vault via client-credentials.

Apps docs: [Configure authorization in a Databricks app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth).

---

## 5. Permissions checklist

- [ ] Foundry endpoint + deployment  
- [ ] Warehouse host/path + table FQNs (live SQL)  
- [ ] If KV: follow [Key Vault bootstrap](key-vault-bootstrap.md) (URL, secrets, Identity A = Secrets User)  
- [ ] Apps: Authorization SP + tenant; users can query UC  
- [ ] ACA: [grant MI warehouse + UC](../api/deploy-and-hosting.md#64-aca-sql-grant-managed-identity-warehouse-uc)  
- [ ] Local: `az login`  
- [ ] Foundry SP only in `EDIM_FOUNDRY_*`  

---

## 6. Troubleshooting (identity)

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Foundry 503 / `DefaultAzureCredential failed` on Apps after SQL works | Identity **B** not in env — App SP (**A**) cannot read KV, or `EDIM_KV_SECRET_MAP` wrong | Find App SP + grant Secrets User: [Key Vault §7](key-vault-bootstrap.md#7-grant-databricks-app-sp-key-vault-secrets-user) |
| SQL OK local, fail Apps | No forwarded **user** token (Identity **U**) | Call via App URL while signed in; open `/docs` on the App URL |
| Apps `RequestError` / OpenSession | User authorization missing scope **`sql`**; or no `X-Forwarded-Access-Token`; or user lacks CAN USE / UC SELECT | Add `sql` scope; re-consent; check `GET /api/v1/debug/sql-auth` |
| Do we need a UI to pass the token? | No — Apps gateway injects the header | Use Swagger at `https://<app-url>/docs` |
| SQL fail ACA | MI not granted warehouse / UC | [Deploy §6.4](../api/deploy-and-hosting.md#64-aca-sql-grant-managed-identity-warehouse-uc) |
| KV / map errors | Wrong URL, map, or vault role | [Key Vault bootstrap](key-vault-bootstrap.md) |
| `dbutils` on Apps | Not available in Apps runtime | Use Key Vault SDK / Apps secrets |
| App SP warehouse CAN MANAGE but SQL still fails | Code uses Identity **U**, not App SP for SQL | Add **user** auth scope `sql` ([Deploy §5.7](../api/deploy-and-hosting.md#57-validate-on-apps-closes-p0-apps-token-check)) |

!!! tip "Pro tip"
    On Apps, always verify `GET /api/v1/debug/sql-auth` → `"forwarded_access_token_present": true` before debugging UC grants.

---

## 7. Related docs

| Doc | Topic |
|-----|--------|
| [Authentication flows](authentication-flows.md) | Visual local / Apps / ACA auth diagrams |
| [Key Vault bootstrap](key-vault-bootstrap.md) | Vault auth order + `EDIM_KV_SECRET_MAP` |
| [Deploy & hosting](../api/deploy-and-hosting.md) | Apps / Docker / ACA packaging + ACA MI grants |
| [Security baseline](security-baseline.md) | App role matrix |
| [Auth and SQL](../architecture/auth-and-sql.md) | Token resolution |
| [Environments](environments.md) | SDBX / DEV / PROD |
| [Env vars](../reference/env-vars.md) | Catalog |

---

## Summary

- **U** = user SQL (Apps forwarded token); **A** = host opens KV; **B** = Foundry SP via `EDIM_FOUNDRY_*`.  
- Do **not** mix Foundry credentials into `AZURE_CLIENT_*`.  
- Apps SQL requires user auth scope **`sql`** — App SP warehouse grants alone are insufficient.  

**Next →** [Authentication flows (C2b-flow)](authentication-flows.md)

<!-- edim-learning-nav -->
---

← [Security baseline](security-baseline.md) · [Authentication flows](authentication-flows.md) →
