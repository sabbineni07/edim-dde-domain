# Windows laptop — dry & live smoke checklist

**Learning path:** H5b · [Guide home](../README.md)  
**← Previous:** [Live smoke](live-smoke-test.md) · **Next:** [Guide home](../README.md) →

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
pip install -e "..\edim-dde-ai[dev,schema]"
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
```

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

```powershell
cd C:\work\edim\edim-dde-api
.\.venv\Scripts\Activate.ps1
# env already loaded from Step 4
uvicorn edim_dde_api.main:app --reload --port 8080
```

Leave this window open. Open a **second** PowerShell for curls.

---

## Step 6 — Validate (dry smoke)

### 5.1 Health

```powershell
curl.exe -sS http://127.0.0.1:8080/health
```

Or:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health | ConvertTo-Json -Depth 5
```

**Pass:** `"status": "ok"` and agents list includes `cluster_tuning`, `spark_rca`.  
Browser OpenAPI: http://127.0.0.1:8080/docs

### 5.2 Dry cluster tuning (Foundry yes, SQL skipped via `metrics`)

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
**Fail 503 `FOUNDRY_LLM_NOT_CONFIGURED`:** fix endpoint / `az login` / deployment name.  
**Tip:** response header `X-Request-Id` matches log lines `[request_id=…]` if you need to debug.

### 5.3 Dry Spark RCA

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
- [ ] `/health` OK  
- [ ] Dry tuning 200  
- [ ] Dry RCA 200  
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
| Foundry 503 | Re-check endpoint (no trailing path mistakes), deployment **name**, `az account show` |

---

← [Live smoke (full)](live-smoke-test.md) · [Guide home](../README.md) →
