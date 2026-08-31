# Deploy & hosting (G3)

**Learning path:** G3 · [Preface](../README.md)  
**← Previous:** [HTTP endpoints](endpoints.md) · **Next:** [Environment variables](../reference/env-vars.md) →

## Chapter summary

This chapter is the **compatibility runbook** for the EDIM DDE API: how to
package wheels, configure env, and run the FastAPI host on Databricks Apps,
Docker Compose, and ACA Native. The target-selection matrix and detailed
runbooks for all three supported hosting options are in
[Deployment targets and release runbook](deployment-targets.md).

**Outcome:** a packaged, configured runtime that passes `/health` and live or
dry agent smoke on its selected host.

**Deploy artifacts (code):** `edim-dde-api/deploy/`

---

## Prerequisites

| Requirement | Chapter / link |
|-------------|----------------|
| Env primer | [Configuration (G1)](configuration.md) |
| Identities U / A / B | [Access & permissions (C2b)](../platform/access-and-permissions.md) |
| Key Vault map | [Key Vault bootstrap (C2c)](../platform/key-vault-bootstrap.md) |
| Local smoke curls | [Live smoke (H5)](../contribute/live-smoke-test.md) |

!!! warning "Secrets"
    Never commit Foundry client secrets or real SP passwords into `app.yaml`. Use Key Vault or Apps secrets.

---

## 1. Approach (one graph package, many hosts)

| Principle | Meaning |
|-----------|---------|
| **One graph package** | YAML, registered nodes, prompts, and domain logic are shared. |
| **Host-specific entrypoint** | ACA Native uses FastAPI; Agent Server uses an allowlisted graph factory; full LangSmith uses its platform runtime. |
| **Env contract** | Warehouse, Foundry, CORS, planes (`EDIM_*`) are **configuration**, not code forks. |
| **Thin host adapters** | Databricks = `app.yaml`; ACA = image + identity; Agent Server = manifest + graph factory. |
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
 Databricks  ACA Native   Agent Server / LangSmith
   Apps       Docker       platform runtime
  app.yaml    same core    packaged graph factory
```

**Do not** fork business logic for a host, bake secrets/UC FQNs into an image,
or select the runtime from an untrusted request.

---

## 2. Target selection (current architecture)

| Target | Status | Primary reason |
|--------|--------|----------------|
| **ACA Native** | **Standard** | Azure networking, managed identity, scaling, and API ownership |
| **Standalone Agent Server on ACA** | Optional | Ready-made LangGraph threads, runs, streaming, and runtime APIs |
| **Full self-hosted LangSmith Deployment on AKS** | Optional | Private LangSmith control plane/UI plus Agent Server |
| **Databricks Apps** | Compatibility path | Data-local pilots and workloads whose tools are entirely in Databricks |

See [Deployment targets and release runbook](deployment-targets.md) before
starting a new deployment. Databricks Apps remains documented below for
existing workloads; it is no longer the default architecture.

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
make vendor-wheels
# equivalent: ./deploy/scripts/build_vendor_wheels.sh
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
| **Azure Container Apps / Docker** | MI — [§6.4 grant steps](#64-aca-sql-grant-managed-identity-warehouse-uc) | Foundry SP → `EDIM_FOUNDRY_*` | ACA **managed identity** |
| **AKS / App Service** (later) | Same pattern as ACA | Same | Workload MI |

Identities U / A / B: [Access & permissions](../platform/access-and-permissions.md)  
Vault / secret map: [Key Vault bootstrap](../platform/key-vault-bootstrap.md)

**Code:** one credential resolver for all hosts — no per-host Python forks. Foundry SP uses `EDIM_FOUNDRY_*` so it does not collide with SQL’s `DefaultAzureCredential`.

### 4.3 Optional planes (target-neutral defaults)

| Variable | Suggested local/ACA Native baseline |
|----------|-----------------------------|
| `EDIM_OBSERVABILITY` | `none` locally; Azure-native telemetry or self-hosted LangSmith by target |
| `EDIM_STATE_STORE` | `postgres` for shared/runtime environments; `memory` only for isolated tests |
| `EDIM_RETRIEVAL` | `none` |
| `EDIM_STRICT_STARTUP` | `1` on deployed environments |
| `EDIM_REQUIRE_SQL` | `1` when you require warehouse for all calls |
| `EDIM_CORS_ORIGINS` | Set only if a browser UI calls the API |

Full catalog: [Environment variables](../reference/env-vars.md) · matrix: [Environments](../platform/environments.md).

### 4.4 Where to set env

| Host | Where |
|------|--------|
| Databricks Apps | `deploy/databricks-app/app.yaml` `env:` **and/or** Apps console → Environment / secrets |
| Docker / ACA | `--env-file`, ACA env settings, Key Vault refs |
| Secrets | Never commit; use Apps secrets or `AZURE_KEY_VAULT_URL` — see [Key Vault bootstrap](../platform/key-vault-bootstrap.md) |

Template values live in `app.yaml` as `REPLACE_*` — replace per workspace before deploy.

---

## 5. Deploy — Databricks Apps (compatibility target)

**Makefile (from `edim-dde-api/`):** `make help` · `make vendor-wheels` · `make apps-create` · `make apps-deploy`  
(see [Makefile targets](#59-makefile-targets-edim-dde-api)).

### 5.1 Prerequisites

- Workspace rights to **create Apps**  
- Databricks CLI ≥ current Apps support (`databricks apps -h`) and a configured profile (`databricks auth login` / `.databrickscfg`)  
- SQL warehouse running; UC tables granted to **App users**  
- Foundry endpoint + deployment; Key Vault with Foundry SP secrets **or** Apps secrets for `EDIM_FOUNDRY_*`  
- Wheels built (`make vendor-wheels`)

### 5.2 Build wheels (required before sync/deploy)

```bash
cd /path/to/edim/edim-dde-api
make vendor-wheels
# equivalent: ./deploy/scripts/build_vendor_wheels.sh
```

Outputs `deploy/databricks-app/vendor/*.whl` + `requirements.vendor.txt`.  
`vendor/` is gitignored — rebuild before each deploy.

### 5.3 What gets deployed (not the Python `src/` tree)

Apps installs from the **`deploy/databricks-app/`** folder. It does **not** upload editable `src/` trees from the three packages.

| Artifact | Role |
|----------|------|
| `app.yaml` | Start command (`uvicorn edim_dde_api.main:app`) + env |
| `requirements.txt` | Includes `-r requirements.vendor.txt` + host pins |
| `requirements.vendor.txt` | Exact `./vendor/*.whl` paths (generated) |
| `vendor/*.whl` | Built `edim-dde-ai`, `edim-dde-domain`, `edim-dde-api` wheels |

`vendor/` is **gitignored** — rebuild with `make vendor-wheels` before each deploy (unless you use Option C below).

**Engineer guide (`/guide`):** MkDocs Material builds into `deploy/docker/guide-site` for **local Docker** (`make guide-site` / `compose-up`). On Databricks Apps, mount is **optional** (`EDIM_MOUNT_GUIDE=1` + copy `guide-site/` into the Apps bundle). Default Apps sync is wheels + `app.yaml` only.

!!! tip "Pro tip — Windows Apps deploy"
    Use `make vendor-wheels-win`, `make apps-sync`, and `make apps-deploy`. `apps-deploy` stops and starts the App after SNAPSHOT deploy so new wheels load. Git Bash rewrites `/Workspace/...` paths — the PowerShell wrapper unmangles them.

### 5.3b Packaging / deploy options

#### Option A — Source bundle upload/sync (**recommended now**)

1. `make vendor-wheels`  
2. Ensure `app.yaml`, `requirements*.txt`, and `vendor/*.whl` are present under `deploy/databricks-app/`  
3. Create app `edim-dde-api-dev` ([§5.4](#54-create-a-new-databricks-app))  
4. Sync that folder to a Workspace path (or upload in the Apps console)  
5. Deploy → Apps installs wheels from `requirements.vendor.txt` → starts FastAPI  

**Manual (Apps console):** create app → Deploy → select the folder that contains `app.yaml` + `vendor/`.  
**CLI:** `make apps-sync` then `make apps-deploy` (see §5.4–5.5).

This is the simplest path for first DEV validation.

#### Option B — Git-backed app source

1. Point the Databricks App at a Git repo/path that contains the same `databricks-app` layout.  
2. On deploy, Apps builds from that folder.

**Caveat:** `vendor/` is not in Git by default. Either:

- Commit/regenerate vendor in a release branch (heavy), or  
- Prefer **Option C** so Git only holds `app.yaml` + version pins.

See [Deploy from a Git repository](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/deploy).

#### Option C — Private package index (**best long-term**)

1. Publish wheels to Artifactory / Azure Artifacts / similar.  
2. Replace `requirements.vendor.txt` with pins, e.g. `edim-dde-api==1.0.0`.  
3. Deploy source **without** vendored wheel blobs.

Documented in [§3.3](#33-later-private-package-index). Track as a follow-on after first successful Apps smoke (product backlog packaging item).

#### Option D — Wheels on Databricks Volume / ADLS (**possible, not first path**)

You *can* store `.whl` files on a UC Volume or ADLS, but Apps dependency install is driven by `requirements.txt` at build/start time. Remote wheels need **custom bootstrap** (download before `pip install`) plus auth to the Volume/ADLS — more failure points than Option A.

| Approach | Use when |
|----------|----------|
| **A — Workspace bundle + `vendor/`** | Now (DEV prove-out) |
| **B — Git** | After Option C, or with a release artifact that includes wheels |
| **C — Private index** | Durable CI/CD |
| **D — Volume/ADLS** | Only if org forbids workspace upload *and* private index is unavailable — design bootstrap first |

**Practical recommendation:** name the app **`edim-dde-api-dev`**, deploy with **Option A**, then migrate packaging to **Option C**.

### 5.4 Create a new Databricks App

**Naming (API vs future UI):** use an **`api`** suffix so a later UI app can coexist:

| Env | API app | Future UI app |
|-----|---------|----------------|
| DEV | `edim-dde-api-dev` | `edim-dde-ui-dev` |
| UAT | `edim-dde-api-uat` | `edim-dde-ui-uat` |
| PROD | `edim-dde-api-prod` | `edim-dde-ui-prod` |

Helps IAM, observability filters, and incident ownership.

**Runtime vs control plane (wording):** the **runtime** is always **FastAPI** (`uvicorn` in `app.yaml`). “Apps console” / create-deploy steps below mean the **Databricks Apps control plane** (web console or CLI) — **not** an Angular/React frontend.

#### A) Manual (Databricks Apps console)

1. Workspace → app switcher → **Databricks Apps** (or **Compute → Apps**).  
2. **Create app** → name **`edim-dde-api-dev`** → description e.g. `EDIM DDE FastAPI (DEV)` → create.  
3. Open the app → **Authorization** → note the **service principal** application (client) ID.  
4. Grant that SP **Key Vault Secrets User** — [Key Vault bootstrap §7](../platform/key-vault-bootstrap.md#7-grant-databricks-app-sp-key-vault-secrets-user).  
5. Fill non-secret env in `app.yaml` (or Apps → Environment). Never commit Foundry client secrets.  
6. Continue with [§5.5 Deploy](#55-deploy-the-app).

#### B) CLI (manual / scripted)

```bash
databricks auth login --host https://<workspace>.azuredatabricks.net

databricks apps create edim-dde-api-dev \
  --description "EDIM DDE FastAPI (DEV)"

cd /path/to/edim/edim-dde-api
make apps-create APP_NAME=edim-dde-api-dev
```

Then Apps console → **Authorization** → copy App SP client ID → [KV grant](../platform/key-vault-bootstrap.md#7-grant-databricks-app-sp-key-vault-secrets-user).

```bash
databricks apps list
databricks apps get edim-dde-api-dev
```

#### C) Automate from CI/CD

| Stage | What to run |
|-------|-------------|
| Build | `make vendor-wheels` |
| Auth | Databricks CLI OAuth / OIDC — not a laptop PAT in logs |
| Sync | Upload `deploy/databricks-app/` (Option A) |
| Create (once) | `databricks apps create edim-dde-api-dev` or create once in console |
| Deploy | `databricks apps deploy … --source-code-path …` |
| Smoke | `curl "$BASE/health"` |

```bash
export APP_NAME=edim-dde-api-dev
export WS_SOURCE=/Workspace/Users/<you>@example.com/apps/${APP_NAME}

make vendor-wheels

databricks workspace import-dir \
  deploy/databricks-app \
  "$WS_SOURCE" \
  --overwrite

databricks apps deploy "$APP_NAME" \
  --source-code-path "$WS_SOURCE" \
  --mode SNAPSHOT
```

**Makefile:** `make apps-sync` · `make apps-deploy` (require `APP_NAME`, `WS_SOURCE`).

```yaml
# CI pseudocode
steps:
  - checkout
  - run: make vendor-wheels
  - run: make apps-sync APP_NAME=edim-dde-api-dev WS_SOURCE=/Workspace/Shared/edim-dde-api-dev
  - run: make apps-deploy APP_NAME=edim-dde-api-dev WS_SOURCE=/Workspace/Shared/edim-dde-api-dev
  - run: curl -sfS "$APP_URL/health"
```

Prefer **create once**; every merge **rebuilds wheels + deploy**.

### 5.5 Deploy the app

After create + env + KV grant + `make vendor-wheels`:

#### Apps console

1. Sync/upload `deploy/databricks-app/` (with `vendor/`) into a workspace folder.  
2. Apps → **`edim-dde-api-dev`** → **Deploy**.  
3. Select the folder that contains `app.yaml` + `requirements.txt` + `vendor/`.  
4. Deploy → wait until **Running**.  
5. Copy the **App URL**.

#### CLI

```bash
make apps-deploy APP_NAME=edim-dde-api-dev \
  WS_SOURCE=/Workspace/Users/<you>/apps/edim-dde-api-dev

# or:
databricks apps deploy edim-dde-api-dev \
  --source-code-path /Workspace/Users/<you>/apps/edim-dde-api-dev \
  --mode SNAPSHOT
```

`--mode SNAPSHOT` is typical for CI; `AUTO_SYNC` for iterative DIY. Confirm with `databricks apps deploy -h`.

### 5.6 `app.yaml` command

```yaml
command:
  - uvicorn
  - edim_dde_api.main:app
  - --host
  - "0.0.0.0"
  - --port
  - "$DATABRICKS_APP_PORT"
```

Databricks substitutes `$DATABRICKS_APP_PORT`. Env for warehouse / Foundry / KV: edit `deploy/databricks-app/app.yaml` (see comments there).

### 5.7 Validate on Apps (closes P0 Apps token check)

#### SQL user-auth prerequisites (before cluster_tuning)

This API uses **user SQL** (Identity U): the Apps gateway injects `X-Forwarded-Access-Token`; code passes that token to the warehouse. You do **not** need a separate UI app, and you do **not** manually set that header.

**Swagger / OpenAPI is fine** if you open it on the **App URL** (Apps → your app → Open → `/docs`). Browser calls from `/docs` to `/api/v1/*` still go through the Apps reverse proxy, which adds the forwarded user token. Opening `/docs` on localhost does **not**.

Warehouse **CAN MANAGE** for the **App service principal** only helps the **app-identity** SQL path. Our code does **not** use `DATABRICKS_CLIENT_*` for SQL, so App SP warehouse grants alone will not fix `cluster_tuning` SQL.

Confirm all of:

1. **App → Authorization → User authorization** → add scope **`sql`** (defaults are only `iam.*` identity reads — not SQL).  
2. Optionally **App → Resources** → add the same SQL warehouse (common Apps setup; often paired with App SP CAN USE/MANAGE). This is **not** a substitute for the `sql` user scope.  
3. Workspace admin has enabled user authorization if required; **restart/redeploy** after adding scopes; open the App once and **consent** when prompted.  
4. **Your user** has **CAN USE** on that warehouse + **SELECT** on the UC metrics tables.  
5. Call via the **App URL** while signed into the workspace (Swagger on App URL counts).

Quick check from Swagger: `GET /api/v1/debug/sql-auth`  
Or:

```bash
export BASE="https://<your-app-url>"
curl -sS "$BASE/api/v1/debug/sql-auth" | python3 -m json.tool
```

**Pass:** `"forwarded_access_token_present": true`.  
**Fail:** missing user-auth/`sql` scope, no consent, or not calling through the App URL.

```bash
curl -sS "$BASE/health" | python3 -m json.tool
```

**Pass:** `"status":"ok"`, agents include `cluster_tuning` / `spark_rca`.

Then live tuning:

```bash
curl -sS "$BASE/api/v1/cluster_tuning/recommend" \
  -H "content-type: application/json" \
  -H "X-Request-Id: apps-live-tuning-001" \
  -d '{"job_id":"<real>","cluster_id":"<real>","include_explanation":false}'
```

**Pass:** HTTP 200 with UC-backed metrics.  
**Fail:** `RequestError` / OpenSession → almost always missing `sql` scope, missing forwarded token, or user warehouse/UC grants — see [Access & permissions](../platform/access-and-permissions.md).

Smoke details: [Live & dry smoke](../contribute/live-smoke-test.md).  
Platform docs: [Configure authorization in a Databricks app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth).

### 5.8 First-deploy checklist (ordered)

1. [ ] `make vendor-wheels`  
2. [ ] Fill `app.yaml` REPLACE_* (no secrets in git)  
3. [ ] Create app **`edim-dde-api-dev`** — [§5.4](#54-create-a-new-databricks-app)  
4. [ ] Grant App SP → Key Vault Secrets User — [KV §7](../platform/key-vault-bootstrap.md#7-grant-databricks-app-sp-key-vault-secrets-user)  
5. [ ] Sync + deploy Option A — [§5.3b](#53b-packaging-deploy-options) / [§5.5](#55-deploy-the-app)  
6. [ ] `GET /health` then live `cluster_tuning/recommend` — [§5.7](#57-validate-on-apps-closes-p0-apps-token-check)  

Official platform docs: [Configure app.yaml](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/app-runtime) · [Deploy an app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/deploy) · [CLI apps](https://docs.databricks.com/aws/en/dev-tools/cli/reference/apps-commands).

### 5.9 Makefile targets (`edim-dde-api`)

| Target | Purpose |
|--------|---------|
| `make help` | List targets |
| `make vendor-wheels` | Build ai + domain + api wheels into `deploy/databricks-app/vendor/` |
| `make apps-create` | `databricks apps create $(APP_NAME)` |
| `make apps-sync` | `import-dir` local bundle → `$(WS_SOURCE)` |
| `make apps-deploy` | Deploy from `$(WS_SOURCE)`, then **stop + start** the App (reload wheels) |
| `make docker-build` | Build API image only |
| `make docker-run` | Run API image alone (no Postgres) |
| `make compose-up` / `compose-down` / `compose-ps` | API + **Postgres** StateStore (both in Docker) |
| `make pg-up` / `pg-down` / `host-run` | **Postgres in Docker** + **API on laptop** (`az login` works) |
| `make e2e-dry` / `e2e-local` | Local container dry E2E (health + tuning + RCA) |
| `make compose-logs` | Tail API + Postgres |

Variables: `APP_NAME`, `WS_SOURCE`, `EDIM_AI_PATH`, `EDIM_DOMAIN_PATH`, `PYTHON`.

---

## 6. Deploy — Docker / ACA Native (standard container target)

Same core wheels and env **names**, different host glue. For the complete ACA
Native production procedure, including ACR, managed identity, workload
profiles, scaling, workers, and rollback, use
[Deployment targets](deployment-targets.md) §4.

**Postgres in this stack:** used only as the optional **control-plane StateStore** (`EDIM_STATE_STORE=postgres`) for agent catalog / sessions — **not** for Databricks SQL / UC telemetry. See [State store](../platform/state-store.md).

### 6.1 Docker Compose (API + Postgres) — recommended locally

Postgres is included as the **control-plane StateStore** (`EDIM_STATE_STORE=postgres`). Use this stack for **local end-to-end** dry smoke (API + Postgres + Foundry; SQL skipped via overrides).

From `edim-dde-api/`:

```bash
# Put Foundry (+ optional Databricks) vars in ../edim-dde-domain/.env
make compose-up          # vendor-wheels + API + Postgres
make e2e-dry             # /health (assert state_store=postgres) + dry tuning + dry RCA
# or one shot:
make e2e-local

make compose-logs        # optional
make compose-down
```

| Target | What it does |
|--------|----------------|
| `make compose-up` | Build/start **api** + **postgres** |
| `make e2e-health` | Wait for `/health`; require `state_store=postgres` |
| `make e2e-dry` | Dry E2E script (`deploy/scripts/e2e_smoke.sh`) |
| `make e2e-local` | `compose-up` then `e2e-dry` |

Compose file: `edim-dde-api/docker-compose.yml`

| Service | Port | Role |
|---------|------|------|
| `api` | 8080 | FastAPI (`edim_dde_api.main:app`) |
| `postgres` | 5432 | StateStore (`postgresql://edim:edim@postgres:5432/edim`) |
| `redis` | 6379 | Optional (`docker compose --profile redis up -d`) |

**Dry E2E** needs Foundry in `.env` (warehouse optional). **Live SQL** against the same containers: set `DATABRICKS_*` in `.env`, recreate `api`, then run live curls from [Live smoke §5](../contribute/live-smoke-test.md) with `BASE=http://127.0.0.1:8080` (and `az login` on the **host** does not inject into the container — use `EDIM_FOUNDRY_*` and, for SQL from the container, a path that works inside Docker, or run live SQL smoke on Apps/host uvicorn).

**Postgres-only** (API on the host via uvicorn — preferred when Docker cannot do `az login`):

```bash
cd edim-dde-api
az login
make host-run    # pg-up + uvicorn; loads ../edim-dde-domain/.env
# make pg-down when finished
```

Underlying compose file: workspace root `docker-compose.state-store.yml`. Do **not** run `compose-up` and `host-run` together (same `edim-postgres` / port 5432).

### 6.2 Build image (without Compose)

```bash
cd /path/to/edim/edim-dde-api
make docker-build
# or: make vendor-wheels && docker build -f deploy/docker/Dockerfile -t edim-dde-api:local .
```

### 6.3 Run image alone

```bash
make docker-run
# or: docker run --rm -p 8080:8080 --env-file ../edim-dde-domain/.env edim-dde-api:local
curl -sS http://127.0.0.1:8080/health
```

Without Compose, default state store is whatever is in `.env` (often `memory`).

### 6.4 ACA SQL — grant managed identity warehouse + UC

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

### 6.5 Azure Container Apps mapping

| Concern | Setting |
|---------|---------|
| Image | Push `edim-dde-api:<version>` to ACR |
| Ingress | External or internal; target port **8080** (or set `PORT`) |
| Env | Same as [§4](#4-configuration-environment) |
| Secrets | Prefer `AZURE_KEY_VAULT_URL` + MI as vault reader — [Key Vault bootstrap](../platform/key-vault-bootstrap.md) |
| SQL auth | Container MI — complete [§6.4](#64-aca-sql-grant-managed-identity-warehouse-uc) |
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

| Host | Adapter files | Status |
|------|---------------|--------|
| Databricks Apps | `deploy/databricks-app/*` | Compatibility |
| ACA Native | `deploy/docker/Dockerfile` | **Standard** |
| Standalone Agent Server | `langsmith_entrypoint.py` + `langgraph.json` | Optional; pilot adapter exists |
| Full self-hosted LangSmith | Vendor platform bundle on AKS | Optional; platform-owned |
| App Service / VMs | No approved adapter | Not supported as standard targets |

---

## 8. What not to do

- Commit secrets or real SP passwords into `app.yaml`  
- Use editable `-e ../edim-dde-*` in production Apps/Docker  
- Fork business logic per cloud  
- Require Unity Catalog as the **control-plane** store (StateStore stays pluggable)  
- Hold long HITL HTTP requests (sessions use StateStore — see [HITL resume](../framework/hitl-resume.md))  
- Expect `apps-deploy` alone to always reload code — stop/start (now in Makefile) is required on some workspaces  

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `/health` OK, new routes 404 after deploy | App process not restarted | `make apps-deploy` (includes stop/start) or Apps UI Stop → Start |
| `Public access is not allowed for workspace` | Opening App URL without workspace session | Open via **Apps → Open app** while signed into Databricks |
| Apps SQL `RequestError` / OpenSession | Missing user auth scope `sql`, no forwarded token, or UC grants | [§5.7](#57-validate-on-apps-closes-p0-apps-token-check); `GET /api/v1/debug/sql-auth` |
| Foundry 503 on Apps, SQL works | Identity B missing — KV grant or secret map | [Key Vault §7](../platform/key-vault-bootstrap.md#7-grant-databricks-app-sp-key-vault-secrets-user) |
| `/Workspace` becomes `C:/Program Files/Git/Workspace` | Git Bash path conversion | Use `make apps-sync` / PowerShell wrapper; or `WS_SOURCE=//Workspace/...` |
| `/guide` 404 on App | Guide not copied / not opted in / old wheel | `make guide-site-win` → `copy-guide-site` → rebuild wheels → sync → deploy; set `EDIM_MOUNT_GUIDE=1` |
| Compose + `host-run` conflict | Both use port 5432 / `edim-postgres` | Use one path only |
| ACA SQL fails | MI not granted warehouse / UC | [§6.4](#64-aca-sql-grant-managed-identity-warehouse-uc) |

---

## 10. Related docs

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

---

## Summary

- **One versioned YAML graph package** feeds every selected host; ai + domain ship as **wheels**.  
- **Standard host:** ACA Native — FastAPI with managed identity and Azure-native operations.  
- **Optional hosts:** Standalone Agent Server on ACA, or full self-hosted LangSmith Deployment on AKS.  
- **Compatibility host:** Databricks Apps — retained for data-local and existing workloads.  
- After deploy, **stop + start** so wheels and optional `/guide` load.  

**Next →** [Environment variables (H1)](../reference/env-vars.md)

<!-- edim-learning-nav -->
---

← [HTTP endpoints](endpoints.md) · [Environment variables](../reference/env-vars.md) →
