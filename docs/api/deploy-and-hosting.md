# Deploy & hosting (Databricks Apps default)

**Learning path:** G3 · [Guide home](../README.md)  
**← Previous:** [HTTP endpoints](endpoints.md) · **Next:** [Environment variables](../reference/env-vars.md) →

How to package and run the EDIM stack on **Databricks Apps** (default first cut), and how the same artifact moves to **Azure Container Apps** or other container hosts with little rework.

**Deploy artifacts (code):** [`edim-dde-api/deploy/`](../../../edim-dde-api/deploy/)

---

## 1. Approach (one app, many hosts)

| Principle | Meaning |
|-----------|---------|
| **One deployable** | Only **`edim-dde-api`** is hosted. It depends on `edim-dde-domain` + `edim-dde-ai` as **wheels**. |
| **Same entrypoint** | Always `uvicorn edim_dde_api.main:app`. |
| **Env contract** | Warehouse, Foundry, CORS, planes (`EDIM_*`) are **configuration**, not code forks. |
| **Thin host adapters** | Databricks = `app.yaml` + port; containers = `Dockerfile` + `PORT`. |
| **Secrets outside Git** | Key Vault / Apps secrets / ACA secret refs → same env **names**. |

How many agents per app (one runtime vs domain split vs hub):  
→ [Agent deployment & composition](../architecture/agent-deployment-and-composition.md)

```text
  wheels (ai + domain + api)
           │
           ▼
  ┌────────────────────────────┐
  │  edim-dde-api (FastAPI)    │
  │  edim_dde_api.main:app     │
  └─────────────┬──────────────┘
                │
     ┌──────────┼──────────┐
     ▼          ▼          ▼
 Databricks  Azure ACA   (AKS / App Service / …)
   Apps       (Docker)
  app.yaml    same image
```

**Do not** deploy three separate services for R1, and do not bake UC FQNs into the image.

---

## 2. Why Databricks Apps is the default (first cut)

| Reason | Detail |
|--------|--------|
| **Auth already matches** | API middleware expects `X-Forwarded-Access-Token` for warehouse SQL — that is the Apps user OAuth path. |
| **Data locality** | SQL warehouse + Unity Catalog tables live in the same workspace you are validating against. |
| **Least new infra** | No container registry or ACA required to prove prod-like SQL + LLM. |
| **P0 gap closure** | Live laptop smoke used `az login`; Apps deploy proves **forwarded user token → SQL**. |
| **Still portable** | The app remains a plain FastAPI process; Docker/ACA reuse the same wheels and env names. |

**Not** “Databricks forever.” Azure Container Apps (or AKS) is the second host when you need VNet isolation, scale rules, or non-Databricks callers with SP/MI auth.

---

## 3. Packaging

### 3.1 What gets built

| Artifact | Role |
|----------|------|
| `edim_dde_ai-*.whl` | Framework |
| `edim_dde_domain-*.whl` | Sources, agents, Foundry, SQL |
| `edim_dde_api-*.whl` | FastAPI host |
| `deploy/databricks-app/` | Apps bundle: `app.yaml`, `requirements.txt`, `vendor/*.whl` |
| `deploy/docker/Dockerfile` | Same wheels → portable image |

### 3.2 Build vendor wheels

From `edim-dde-api` (siblings `edim-dde-ai` / `edim-dde-domain` next to it):

```bash
cd /path/to/edim/edim-dde-api
./deploy/scripts/build_vendor_wheels.sh
```

If siblings live elsewhere:

```bash
export EDIM_AI_PATH=/path/to/edim-dde-ai
export EDIM_DOMAIN_PATH=/path/to/edim-dde-domain
./deploy/scripts/build_vendor_wheels.sh
```

**Windows (Git Bash or WSL):**

```bash
bash deploy/scripts/build_vendor_wheels.sh
```

Outputs:

- `deploy/databricks-app/vendor/*.whl`
- `deploy/databricks-app/requirements.vendor.txt` (exact filenames for pip)

`vendor/` is gitignored — rebuild before each deploy (or publish wheels to a private index later and drop vendoring).

### 3.3 Later: private package index

When you have Artifactory / Azure Artifacts:

1. `twine upload` the three wheels.  
2. Replace `requirements.vendor.txt` with version pins, e.g. `edim-dde-api==1.0.0`.  
3. Same `app.yaml` / Dockerfile — only the install source changes.

---

## 4. Configuration & environment

### 4.1 Required for a useful Apps / container deploy

| Variable | Purpose |
|----------|---------|
| `EDIM_ENV` | `sdbx` \| `dev` \| `prod` (ops label) |
| `DATABRICKS_HOST` | Workspace hostname |
| `DATABRICKS_HTTP_PATH` | SQL warehouse path |
| `DATABRICKS_JOB_CLUSTER_METRICS_TABLE` | UC FQN for tuning |
| `AZURE_OPENAI_ENDPOINT` | Foundry endpoint |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Deployment name |

For live RCA on the host, also set spark metrics/logs table FQNs.

### 4.2 Auth matrix by host

| Host | SQL warehouse | Foundry LLM | Opens Key Vault |
|------|---------------|-------------|-----------------|
| **Local machine** | `az login` → `DefaultAzureCredential` | `az login` or `EDIM_FOUNDRY_*` | Optional MI/user via `DefaultAzureCredential` |
| **Databricks Apps** | **User** `X-Forwarded-Access-Token` | Foundry SP → `EDIM_FOUNDRY_*` (KV or Apps secrets) | App SP `DATABRICKS_CLIENT_*` |
| **Azure Container Apps / Docker** | MI — [§6.3 grant steps](#63-aca-sql--grant-managed-identity-warehouse--uc) | Foundry SP → `EDIM_FOUNDRY_*` | ACA **managed identity** |
| **AKS / App Service** (later) | Same pattern as ACA | Same | Workload MI |

Identities U / A / B: [Access & permissions](../platform/access-and-permissions.md)  
Vault / secret map: [Key Vault bootstrap](../platform/key-vault-bootstrap.md)

**Code:** one credential resolver for all hosts — no per-host Python forks. Foundry SP uses `EDIM_FOUNDRY_*` so it does not collide with SQL’s `DefaultAzureCredential`.

### 4.3 Optional planes (first cut defaults)

| Variable | Suggested first Apps deploy |
|----------|-----------------------------|
| `EDIM_OBSERVABILITY` | `none` (turn on LangSmith when BL-029 is ready) |
| `EDIM_STATE_STORE` | `memory` |
| `EDIM_RETRIEVAL` | `none` |
| `EDIM_STRICT_STARTUP` | `1` on DEV/PROD |
| `EDIM_REQUIRE_SQL` | `1` when you require warehouse for all calls |
| `EDIM_CORS_ORIGINS` | Set only if a browser UI calls the API |

Full catalog: [Environment variables](../reference/env-vars.md) · matrix: [Environments](../platform/environments.md).

### 4.4 Where to set env

| Host | Where |
|------|--------|
| Databricks Apps | `deploy/databricks-app/app.yaml` `env:` **and/or** Apps UI → Environment / secrets |
| Docker / ACA | `--env-file`, ACA env settings, Key Vault refs |
| Secrets | Never commit; use Apps secrets or `AZURE_KEY_VAULT_URL` — see [Key Vault bootstrap](../platform/key-vault-bootstrap.md) |

Template values live in `app.yaml` as `REPLACE_*` — replace per workspace before deploy.

---

## 5. Deploy — Databricks Apps (default)

### 5.1 Prerequisites

- Workspace admin / rights to create Apps  
- SQL warehouse running; UC tables granted to App users  
- Foundry endpoint + deployment; SP or Key Vault for non-interactive Foundry  
- Wheels built (§3.2)

### 5.2 Files to sync

Upload or Git-deploy the contents of:

```text
edim-dde-api/deploy/databricks-app/
  app.yaml
  requirements.txt
  requirements.vendor.txt
  vendor/*.whl
  README.md
```

Official platform docs: [Configure app.yaml](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/app-runtime), [Deploy an app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/deploy).

### 5.3 `app.yaml` command

```yaml
command:
  - uvicorn
  - edim_dde_api.main:app
  - --host
  - "0.0.0.0"
  - --port
  - "$DATABRICKS_APP_PORT"
```

Databricks substitutes `$DATABRICKS_APP_PORT` and typically sets `UVICORN_HOST` / `UVICORN_PORT`.

### 5.4 Create and deploy (UI sketch)

1. Workspace → **Compute** / **Apps** → **Create app**.  
2. Point source at the synced `databricks-app` folder (or Git ref that contains it).  
3. Confirm `requirements.txt` is at the app root Databricks builds from.  
4. Set/replace env in UI if you prefer not to bake non-secret config into `app.yaml`.  
5. Deploy; wait until status is running.  
6. Open the App URL.

### 5.5 Create and deploy (CLI sketch)

Exact CLI flags vary by CLI version; pattern:

```bash
# After syncing deploy/databricks-app to workspace path or using source-code path
databricks apps deploy <app-name>  # see current CLI help for your cloud
```

Prefer following your workspace’s current [Deploy a Databricks app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/deploy) page for the precise command.

### 5.6 Validate on Apps (closes P0 Apps token check)

```bash
export BASE="https://<your-app-url>"   # from Apps overview

curl -sS "$BASE/health"
```

**Pass:** `"status":"ok"`, agents include `cluster_tuning` / `spark_rca`.

Then, **while authenticated as an App user** (browser session or token the gateway forwards):

```bash
# Live tuning — NO metrics override — SQL must use forwarded user token
curl -sS "$BASE/api/v1/recommendations" \
  -H "content-type: application/json" \
  -H "X-Request-Id: apps-live-tuning-001" \
  -d '{"job_id":"<real>","cluster_id":"<real>","include_explanation":false}'
```

**Pass:** HTTP 200 with UC-backed `job_cluster_metrics`.  
**Fail with Databricks not configured / auth errors:** warehouse path, grants, or missing forwarded access token (local `az login` does **not** apply inside the App for user SQL).

Dry override still works on Apps if you need a Foundry-only check without SQL.

Smoke details: [Live & dry smoke](../contribute/live-smoke-test.md).

---

## 6. Deploy — Docker / Azure Container Apps (second host)

Same wheels, same env **names**, different glue.

### 6.1 Build image

```bash
cd /path/to/edim/edim-dde-api
./deploy/scripts/build_vendor_wheels.sh
docker build -f deploy/docker/Dockerfile -t edim-dde-api:local .
```

### 6.2 Run locally

```bash
docker run --rm -p 8080:8080 --env-file ../edim-dde-domain/.env edim-dde-api:local
curl -sS http://127.0.0.1:8080/health
```

### 6.3 ACA SQL — grant managed identity warehouse + UC

On ACA there is no Databricks Apps user token. SQL authenticates as the container **managed identity** (Identity A) via `DefaultAzureCredential`. Foundry stays on `EDIM_FOUNDRY_*` (Identity B).

```text
ACA MI ──► Key Vault (Secrets User) ──► EDIM_FOUNDRY_* ──► Foundry LLM
ACA MI ──► Databricks AAD token     ──► SQL warehouse + UC tables
```

Do **not** set `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` on the container (that would steal SQL away from the MI).

**Steps:**

1. **Enable MI** — Container App → **Identity** → system-assigned **On**, or attach a user-assigned MI.  
2. **Copy Application (client) ID** — for system-assigned, open the linked managed identity / enterprise app and copy **Application (client) ID** (not only Object ID). For user-assigned, use the MI resource **Client ID**.  
3. **Register in Databricks** — Account console → **User management** → **Service principals** → add Microsoft Entra ID application with that client ID → assign to the workspace.  
4. **Warehouse Can Use** — SQL Warehouses → warehouse → **Permissions** → add the SP → **Can Use**.  
5. **Unity Catalog** — as metastore admin / owner:

```sql
-- Replace <mi-app-client-id> with the MI Application (client) ID
GRANT USE CATALOG ON CATALOG my_catalog TO `<mi-app-client-id>`;
GRANT USE SCHEMA ON SCHEMA my_catalog.my_schema TO `<mi-app-client-id>`;
GRANT SELECT ON TABLE my_catalog.my_schema.job_cluster_metrics TO `<mi-app-client-id>`;
-- Add SELECT for spark_metrics / spark_logs as needed
```

6. **Key Vault** — same MI → role **Key Vault Secrets User**.  
7. **Smoke** — invoke an agent on the ACA URL; warehouse/permission errors usually mean step 4 or 5.

UC privilege reference: [Manage privileges in Unity Catalog](https://learn.microsoft.com/en-us/azure/databricks/data-governance/unity-catalog/manage-privileges/).  
Identities overview: [Access & permissions](../platform/access-and-permissions.md).

### 6.4 Azure Container Apps mapping

| Concern | Setting |
|---------|---------|
| Image | Push `edim-dde-api:<version>` to ACR |
| Ingress | External or internal; target port **8080** (or set `PORT`) |
| Env | Same as [§4](#4-configuration--environment) |
| Secrets | Prefer `AZURE_KEY_VAULT_URL` + MI as vault reader — [Key Vault bootstrap](../platform/key-vault-bootstrap.md) |
| SQL auth | Container MI — complete [§6.3](#63-aca-sql--grant-managed-identity-warehouse--uc) |
| Foundry | Foundry SP from KV into `EDIM_FOUNDRY_*` |
| Scaling | HTTP scale rules on `/health` or request rate |

No application code change vs Apps if the env contract is honored — only identity wiring differs.

---

## 7. Flexibility checklist (host swap)

When adding a new host, only verify:

1. Process starts with `uvicorn edim_dde_api.main:app` on the platform port.  
2. All required env vars from §4 are set.  
3. Secrets injection uses the **same names**.  
4. `/health` returns agents.  
5. Auth path for SQL is documented for that host (Apps token vs SP/MI).

| Host | Adapter files | Effort |
|------|---------------|--------|
| Databricks Apps | `deploy/databricks-app/*` | Default |
| ACA / Docker | `deploy/docker/Dockerfile` | Rebuild image + map env |
| AKS | Same image + Deployment/Service YAML (add when needed) | Config only |
| App Service | Same image or `az webapp` with startup command | Config only |

---

## 8. What not to do

- Commit secrets or real SP passwords into `app.yaml`  
- Use editable `-e ../edim-dde-*` in production Apps/Docker  
- Fork business logic per cloud  
- Require Unity Catalog as the **control-plane** store (StateStore stays pluggable)  
- Hold long HITL HTTP requests (future sessions use StateStore — see HITL notes in [yaml-schema](../framework/yaml-schema.md))

---

## 9. Related docs

| Doc | Use |
|-----|-----|
| [Configuration](configuration.md) | Local env primer |
| [Environments](../platform/environments.md) | SDBX / DEV / PROD matrix |
| [Security baseline](../platform/security-baseline.md) | App role matrix |
| [**Access & permissions**](../platform/access-and-permissions.md) | Identities U / A / B by host |
| [Key Vault bootstrap](../platform/key-vault-bootstrap.md) | Vault load + `EDIM_KV_SECRET_MAP` |
| [Agent deployment & composition](../architecture/agent-deployment-and-composition.md) | One vs many apps; cross-app SDLC |
| [Live smoke](../contribute/live-smoke-test.md) | Validation curls |
| [Windows smoke](../contribute/windows-smoke-checklist.md) | Windows local path |

<!-- edim-learning-nav -->
---

← [HTTP endpoints](endpoints.md) · [Guide home](../README.md) · [Environment variables](../reference/env-vars.md) →
