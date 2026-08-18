# Windows laptop — dry & live smoke checklist

**Learning path:** H5b · [Guide home](../README.md)  
**← Previous:** [Live smoke](live-smoke-test.md) · **Next:** [Packaging](packaging.md) →

**Audience:** engineers validating EDIM DDE from a **Windows** machine  
**Full reference:** [live-smoke-test.md](live-smoke-test.md)  
**Time:** dry ~20–40 min · live +30–60 min  

Use PowerShell (recommended) or Windows Terminal. Adjust drive letters/paths to your checkout.

---

## Step 1 — Collect configuration (before installing)

Fill this table offline (Teams/OneNote/password manager). **Do not commit secrets to Git.**

### A. Always required (dry + live)

| # | What | Where you get it | Paste into |
|---|------|------------------|------------|
| 1 | Foundry / Azure OpenAI **endpoint** URL | Azure Portal → your Azure OpenAI or AI Foundry resource → **Keys and Endpoint** → Endpoint (e.g. `https://myname.openai.azure.com`) | `AZURE_OPENAI_ENDPOINT` |
| 2 | **Deployment name** | Same resource → **Model deployments** → the **deployment name** column (often `gpt-4o`, not the model family alone) | `AZURE_OPENAI_DEPLOYMENT_NAME` |
| 3 | Azure login works | Install [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli-windows), then `az login` | Auth for Foundry (and SQL when live) |
| 4 | Code checkouts | Git clones of `edim-dde-ai`, `edim-dde-domain`, `edim-dde-api` as **siblings** under one folder | Local paths |

### B. Live smoke only (Databricks SQL)

| # | What | Where you get it | Paste into |
|---|------|------------------|------------|
| 5 | Workspace host | Databricks URL without `https://` — e.g. `adb-….azuredatabricks.net` | `DATABRICKS_HOST` |
| 6 | SQL warehouse HTTP path | Databricks → **SQL Warehouses** → warehouse → **Connection details** → HTTP path (`/sql/1.0/warehouses/…`) | `DATABRICKS_HTTP_PATH` |
| 7 | Job cluster metrics table FQN | Ask data eng / UC browser — form `catalog.schema.table` | `DATABRICKS_JOB_CLUSTER_METRICS_TABLE` |
| 8 | Spark metrics + logs FQNs | Same for RCA | `DATABRICKS_SPARK_METRICS_TABLE`, `DATABRICKS_SPARK_LOGS_TABLE` |
| 9 | Real `job_id` + `cluster_id` | Jobs UI or `SELECT … LIMIT 5` on metrics table | Live tuning JSON body |
| 10 | Real `job_run_id` (+ date) | Failed/slow job run | Live RCA JSON body |

If you only have Foundry today → do **Dry smoke** (Step 4+). Add B later for **Live**.

---

## Step 2 — Tools on Windows

1. Install **Python 3.10+** from python.org (check “Add python.exe to PATH”).
2. Install **Git for Windows**.
3. Install **Azure CLI**, then open a **new** PowerShell:

```powershell
python --version
az version
az login
az account show
```

Confirm the correct subscription/tenant.

4. Clone or sync the three packages under one parent, e.g.:

```text
C:\work\edim\
  edim-dde-ai\
  edim-dde-domain\
  edim-dde-api\
  docker-compose.state-store.yml   # workspace root (Postgres-only)
```

5. **Docker Desktop** (for Postgres StateStore on the host-API path). Confirm:

```powershell
docker version
docker compose version
```

### Corporate package index / trusted host (optional but common)

If your laptop installs Python packages through Artifactory, set these in the same shell before `pip install`:

```powershell
$env:PIP_INDEX_URL = "https://prod.artifactory.nfcu.net/artifactory/api/pypi/pypi/simple"
$env:PIP_TRUSTED_HOST = "prod.artifactory.nfcu.net"
```

This setting is typically **install-time only** (pip). It is not a framework runtime requirement.

### Corporate HTTP proxy (environment-dependent)

If your network requires outbound proxy routing:

```powershell
$env:HTTP_PROXY = "http://binnacle.nfcu.net:8080"
$env:HTTPS_PROXY = "http://binnacle.nfcu.net:8080"
$env:NO_PROXY = "127.0.0.1,localhost"
```

Observed in real smoke runs: this proxy may return `407 Proxy Authentication Required` for Databricks/Azure SDK paths unless proxy auth is fully configured for Python runtime traffic. If you see 407, clear proxy vars for the smoke shell and use a direct path approved by your network team.

```powershell
Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
```

---

## Step 3 — Create venv and install

```powershell
cd C:\work\edim\edim-dde-api
python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install -U pip
pip install -r requirements.txt
pip install -e ".[dev]"
pip install -e "..\edim-dde-domain[azure,databricks,llm,dev]"
pip install -e "..\edim-dde-ai[dev,schema,postgres]"
```

If PowerShell blocks scripts:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Sanity:

```powershell
python -c "import edim_dde_ai, edim_dde_domain, edim_dde_api; print('ok')"
```

Optional unit tests (offline stub — not a substitute for smoke):

```powershell
cd C:\work\edim\edim-dde-domain; pytest -q
cd C:\work\edim\edim-dde-api; pytest -q
```

---

## Step 4 — Configure env (this is where you paste values)

### Option A — `.env` file (recommended)

```powershell
cd C:\work\edim\edim-dde-domain
copy .env.example .env
notepad .env
```

Edit at least:

```text
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o

# Live only — leave blank for dry:
# DATABRICKS_HOST=adb-….azuredatabricks.net
# DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/….
# DATABRICKS_JOB_CLUSTER_METRICS_TABLE=catalog.schema.job_cluster_metrics
# DATABRICKS_SPARK_METRICS_TABLE=catalog.schema.spark_metrics
# DATABRICKS_SPARK_LOGS_TABLE=catalog.schema.spark_logs

# LangSmith (optional — see docs/platform/langsmith-setup.md):
# EDIM_OBSERVABILITY=langsmith
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_API_KEY=...
# LANGCHAIN_PROJECT=edim-dde-dev
# LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
# Do NOT set EDIM_LANGSMITH_ENABLED=auto (only unset or false)
```

If using Key Vault bootstrap, verify secret-map order is:

```text
EDIM_KV_SECRET_MAP=ENV_VAR_NAME:vaultSecretName
```

Example:

```text
EDIM_KV_SECRET_MAP=EDIM_FOUNDRY_CLIENT_ID:DLABS-DIM-ADB-APP-AIF-APPID,EDIM_FOUNDRY_CLIENT_SECRET:DLABS-DIM-ADB-APP-AIF-APPKEY
```

Do not reverse this order.

Load into the **same** PowerShell that will run uvicorn:

```powershell
Get-Content C:\work\edim\edim-dde-domain\.env | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $k, $v = $_ -split '=', 2
  [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), 'Process')
}
```

### Option B — set in session

```powershell
$env:AZURE_OPENAI_ENDPOINT = "https://YOUR-RESOURCE.openai.azure.com"
$env:AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4o"
# Live:
# $env:DATABRICKS_HOST = "adb-….azuredatabricks.net"
# $env:DATABRICKS_HTTP_PATH = "/sql/1.0/warehouses/…"
# $env:DATABRICKS_JOB_CLUSTER_METRICS_TABLE = "catalog.schema.job_cluster_metrics"
```

Optional fail-fast:

```powershell
$env:EDIM_STRICT_STARTUP = "1"
# Live warehouse required:
# $env:EDIM_REQUIRE_SQL = "1"
```

---

## Step 5 — Start API

### 5a — Recommended: Postgres in Docker + API on laptop (`az login` works)

This is the path when Docker cannot run `az login` (proxy/kernel). Postgres runs in a container; uvicorn runs in PowerShell and uses your host Azure CLI.

**Terminal 1 — Postgres:**

```powershell
cd C:\work\edim
docker compose -f docker-compose.state-store.yml up -d
docker compose -f docker-compose.state-store.yml ps
# wait until postgres is healthy / pg_isready
```

**Terminal 2 — API (after Steps 3–4 + `az login`):**

```powershell
cd C:\work\edim\edim-dde-api
.\.venv\Scripts\Activate.ps1
# env already loaded from Step 4
$env:EDIM_STATE_STORE = "postgres"
$env:EDIM_DATABASE_URL = "postgresql://edim:edim@127.0.0.1:5432/edim"
# optional — inherits state store if unset:
# $env:EDIM_RECOMMENDATION_STORE = "postgres"

uvicorn edim_dde_api.main:app --reload --port 8080
```

**Git Bash alternative** (if you have `make`):

```bash
cd /c/work/edim/edim-dde-api
source .venv/Scripts/activate
az login
make host-run
```

Leave the API window open. Open a **third** PowerShell for curls (Step 6).

When finished: `Ctrl+C` in the API window, then:

```powershell
cd C:\work\edim
docker compose -f docker-compose.state-store.yml down
```

### 5b — API only (in-memory store — no Docker)

```powershell
cd C:\work\edim\edim-dde-api
.\.venv\Scripts\Activate.ps1
# env already loaded from Step 4
uvicorn edim_dde_api.main:app --reload --port 8080
```

Leave this window open. Open a **second** PowerShell for curls.

---

## Step 6 — Validate (dry smoke)

### 6.1 Health

```powershell
curl.exe -sS http://127.0.0.1:8080/health
```

Expect JSON with `"status":"ok"`. If you used Step 5a (Postgres):

```text
"state_store": "postgres"
"recommendation_store": "postgres"
```

Or:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health | ConvertTo-Json -Depth 5
```

**Pass:** `"status": "ok"` and agents list includes `cluster_tuning`, `spark_rca`.  
Browser OpenAPI: http://127.0.0.1:8080/docs

### 6.2 Dry cluster tuning (Foundry yes, SQL skipped via `metrics`)

Save body to a file to avoid PowerShell quoting pain:

```powershell
@'
{
  "job_id": "dry-job-1",
  "cluster_id": "dry-cluster-1",
  "include_explanation": false,
  "metrics": {
    "azure_worker_vm_size": "Standard_E8s_v3",
    "max_worker_nodes_provisioned": 16,
    "avg_worker_nodes_consumed": 4.0,
    "p99_worker_nodes_consumed": 5.0,
    "peak_worker_cpu_utilization_pct": 20,
    "peak_worker_memory_utilization_pct": 25,
    "avg_worker_cpu_utilization_pct": 15,
    "avg_worker_memory_utilization_pct": 18,
    "driver_node_count": 1
  }
}
'@ | Set-Content -Encoding utf8 C:\temp\edim-tuning-dry.json

curl.exe -sS http://127.0.0.1:8080/api/v1/cluster_tuning/recommend `
  -H "content-type: application/json" `
  -H "X-Request-Id: win-dry-tuning-001" `
  --data-binary "@C:\temp\edim-tuning-dry.json"
```

**Pass:** HTTP 200, JSON has `recommendation`, `risk_assessment` / `reason_codes`.  
With Step 5a Postgres: also expect `recommendation_id` + `recommendation_status` = `proposed`, then:

```powershell
curl.exe -sS "http://127.0.0.1:8080/api/v1/cluster_tuning/recommendations?job_id=dry-job-1"
```

**Fail 503 `FOUNDRY_LLM_NOT_CONFIGURED`:** fix endpoint / `az login` / deployment name.  
**Tip:** response header `X-Request-Id` matches log lines `[request_id=…]` if you need to debug.

### 6.3 Dry Spark RCA

```powershell
@'
{
  "job_run_id": "dry-jr-1",
  "job_id": "dry-job-1",
  "evidence_pack": {
    "job_run_id": "dry-jr-1",
    "evidence": [
      {"ref": "e1", "excerpt": "Executor OutOfMemoryError: Java heap space"}
    ],
    "raw_anchors": {
      "failure_reason": "Executor OutOfMemoryError: Java heap space"
    }
  }
}
'@ | Set-Content -Encoding utf8 C:\temp\edim-rca-dry.json

curl.exe -sS http://127.0.0.1:8080/api/v1/rca/analyze `
  -H "content-type: application/json" `
  -H "X-Request-Id: win-dry-rca-001" `
  --data-binary "@C:\temp\edim-rca-dry.json"
```

**Pass:** HTTP 200 with `root_cause` and `recommended_actions`.  
**Tip:** response `X-Request-Id` ↔ log lines `[request_id=…]`.

---

## Step 6b — Validate LangSmith (optional)

Full reference: [LangSmith setup guide](../platform/langsmith-setup.md).

Prerequisites: LangSmith vars in `.env` (Step 4), API running (Step 5), dry tuning call succeeded (Step 6).

1. **Health**

```powershell
curl.exe -sS http://127.0.0.1:8080/health
```

Pass: JSON contains `"observability": "langsmith"`. If `"none"`, reload `.env` in the uvicorn shell (Step 4 loader) and restart.

2. **Correlated dry call** (if you skipped Step 6 tuning):

```powershell
curl.exe -sS -D - http://127.0.0.1:8080/api/v1/cluster_tuning/recommend `
  -H "content-type: application/json" `
  -H "X-Request-Id: langsmith-win-001" `
  --data-binary "@C:\temp\edim-tuning-dry.json"
```

3. **LangSmith UI**

- Sidebar **Application** → **My First App** (not **All Applications**)
- Open **Tracing** → project matching **`LANGCHAIN_PROJECT`** from `.env`
- Find run **`cluster_tuning`**; metadata `request_id` = `langsmith-win-001`

**Common mistakes:** using `LANGSMITH_TRACING` without `LANGCHAIN_TRACING_V2`; looking under wrong Application; expecting OpenAI Agents SDK layout (EDIM uses LangGraph — see setup guide §2).

---

## Step 7 — Live smoke (after §B filled)

1. Ensure warehouse is **running** and your AAD user can `SELECT` the tables.
2. In Databricks SQL editor, run:

```sql
SELECT * FROM <your_job_cluster_metrics_table> LIMIT 5;
```

Copy a real `job_id` / `cluster_id`.

3. Set Databricks env vars (Step 4), restart uvicorn.
4. Call **without** `metrics`:

```powershell
@'
{
  "job_id": "REPLACE_JOB_ID",
  "cluster_id": "REPLACE_CLUSTER_ID",
  "include_explanation": false
}
'@ | Set-Content -Encoding utf8 C:\temp\edim-tuning-live.json

curl.exe -sS http://127.0.0.1:8080/api/v1/cluster_tuning/recommend `
  -H "content-type: application/json" `
  -H "X-Request-Id: win-live-tuning-001" `
  --data-binary "@C:\temp\edim-tuning-live.json"
```

**Pass:** 200 and `job_cluster_metrics` looks like real UC data.  
5. RCA live: same pattern without `evidence_pack`, with real `job_run_id`.

---

## Step 8 — Tick list (send to team when done)

- [ ] `az login` OK on this laptop  
- [ ] `.env` / env vars set (Foundry at minimum)  
- [ ] *(recommended)* Docker Postgres up; `/health` shows `state_store`/`recommendation_store` = `postgres`  
- [ ] `/health` OK  
- [ ] Dry tuning 200 (+ `recommendation_id` if Postgres)  
- [ ] Dry RCA 200  
- [ ] *(optional)* LangSmith: `/health` → `observability: langsmith`; trace in `LANGCHAIN_PROJECT` ([Step 6b](#step-6b--validate-langsmith-optional))  
- [ ] *(optional)* Live tuning 200  
- [ ] *(optional)* Live RCA 200  
- [ ] Note request ids + date + dry vs live  

If blocked, send: mode, `/health` JSON, HTTP status, `error_code`, request id — **no secrets**.

---

## Common Windows issues

| Issue | Fix |
|-------|-----|
| `Activate.ps1` cannot run | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `curl` is an alias | Use `curl.exe` |
| JSON quoting hell | Use `--data-binary "@file.json"` as above |
| uvicorn not found | Activate venv; `pip install uvicorn` via api requirements |
| Port 8080 in use | `--port 8081` and change URLs |
| Docker / Postgres fail | Start Docker Desktop; `docker compose -f ..\docker-compose.state-store.yml ps`; free port 5432 |
| `psycopg` missing | `pip install -e "..\edim-dde-ai[postgres]"` |
| Foundry 503 | Re-check endpoint (no trailing path mistakes), deployment **name**, `az account show` |
| `/health` → `observability: none` | Load `.env` in uvicorn shell; `LANGCHAIN_TRACING_V2=true`; see [LangSmith setup §7](../platform/langsmith-setup.md#71-confirm-process-config) |
| No traces in LangSmith | Use **My First App** (not All Applications); match `LANGCHAIN_PROJECT`; keep `LANGCHAIN_TRACING_V2` |
| `EDIM_LANGSMITH_ENABLED=auto` | Remove — only unset or `false` is valid |

---

← [Live smoke (full)](live-smoke-test.md) · [Guide home](../README.md) · [Packaging](packaging.md) →
