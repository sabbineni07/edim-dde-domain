# Live & dry smoke test guide

**Audience:** any engineer validating EDIM DDE on a laptop or against a shared non-prod stack  
**Related:** [Quickstart](../getting-started/quickstart.md) · [Configuration](../api/configuration.md) · [Env vars](../reference/env-vars.md) · [Testing](testing.md)

This runbook proves the stack works **beyond unit tests**: API up, agents registered, Foundry reachable (when live), and optionally Databricks SQL.

**On Windows?** Prefer the PowerShell-oriented checklist: [windows-smoke-checklist.md](windows-smoke-checklist.md).

---

## 1. Choose a mode

| Mode | Databricks SQL | Azure Foundry LLM | What it proves | Typical time |
|------|----------------|-------------------|----------------|--------------|
| **Dry smoke** | Skipped via `metrics` / `evidence_pack` overrides | **Required** (real Foundry) | API → graph → sizing/RCA LLM → response DTO | ~15–30 min |
| **Live smoke** | **Required** (warehouse + UC tables) | **Required** | Full path including SQL collect | ~30–60 min |
| **Offline only** | N/A | Stub (`DomainStubLLM`) | CI / laptop without cloud | `pytest` only — see [Testing](testing.md) |

> **Important:** Dry ≠ offline. Dry skips the **warehouse** only. `uvicorn` always uses Foundry for bundled agents. True offline = `pytest` with `DomainStubLLM`.

**Startup env validation** (runs on API lifespan) only checks that env **strings are present**. It does **not** open Databricks or Foundry connections. Default = log warnings. `EDIM_STRICT_STARTUP=1` fails process start if Foundry endpoint is missing (optional `EDIM_REQUIRE_SQL=1` also requires warehouse host/path).

---

## 2. Information checklist (what you need & where to get it)

Copy this table and fill values with your team / Azure / Databricks admins. **Do not commit secrets.**

### 2.1 Always needed (dry + live)

| # | Value | Example | Where to get it | Configure as |
|---|--------|---------|-----------------|--------------|
| 1 | Azure subscription / tenant access | — | Your org IAM; you must be able to `az login` **or** receive an SP | Auth for Foundry (and SQL when live local) |
| 2 | Foundry / Azure OpenAI **endpoint** | `https://my-foundry.openai.azure.com` | Azure Portal → Azure OpenAI / AI Foundry resource → **Keys and Endpoint** → Endpoint | `AZURE_OPENAI_ENDPOINT` |
| 3 | **Deployment name** (model) | `gpt-4o` | Same resource → **Deployments** → name column (not the model SKU alone) | `AZURE_OPENAI_DEPLOYMENT_NAME` |
| 4 | Foundry auth | `az login` **or** SP triple | Local: Azure CLI. Prod: Key Vault → `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` | env or Key Vault map |
| 5 | Sibling repos checked out | `edim-dde-ai`, `edim-dde-domain`, `edim-dde-api` | Git remotes / workspace folder | local paths |

### 2.2 Live smoke only (SQL)

| # | Value | Example | Where to get it | Configure as |
|---|--------|---------|-----------------|--------------|
| 6 | Workspace **hostname** | `adb-1234567890123456.7.azuredatabricks.net` | Databricks → workspace URL (strip `https://`) **or** Admin → Workspace settings | `DATABRICKS_HOST` |
| 7 | SQL warehouse **HTTP path** | `/sql/1.0/warehouses/abc123def456` | Databricks → **SQL Warehouses** → your warehouse → **Connection details** → HTTP path | `DATABRICKS_HTTP_PATH` |
| 8 | Job cluster metrics **table FQN** | `main.edim.job_cluster_metrics` | Data eng / UC catalog browser; must match columns in `cluster_tuning.agent.yaml` SELECT | `DATABRICKS_JOB_CLUSTER_METRICS_TABLE` |
| 9 | Spark metrics / logs FQNs (RCA) | `main.edim.spark_metrics` | Same — for `spark_rca` live path | `DATABRICKS_SPARK_METRICS_TABLE`, `DATABRICKS_SPARK_LOGS_TABLE` |
| 10 | A real **job_id** + **cluster_id** (tuning) | from recent job run | Databricks Jobs UI → run → cluster details; or `SELECT` top row from metrics table | request body |
| 11 | A real **job_run_id** (RCA) | from failed run | Jobs UI or spark tables | request body |

**FQN rules:** `catalog.schema.table` or `schema.table`; letters, digits, underscore only (validated at SQL interpolate).

### 2.3 Optional

| Value | Where | Env |
|-------|-------|-----|
| LangSmith API key + project | [smith.langchain.com](https://smith.langchain.com) → Settings → API Keys; create project `edim-dde-dev` | `EDIM_OBSERVABILITY=langsmith`, `LANGCHAIN_*` |
| CORS origin | Your local UI URL | `EDIM_CORS_ORIGINS` |
| Key Vault URL | Azure Portal → Key Vault | `AZURE_KEY_VAULT_URL` + `EDIM_KV_SECRET_MAP` |
| Apps forwarded token | Only when calling a **deployed** Databricks App | Header `X-Forwarded-Access-Token` (gateway sets this; you don’t invent it locally) |

---

## 3. Local machine setup

### 3.1 Tools

- Python **3.10+** (`python3 --version`)
- Git
- Azure CLI (`az version`) for local auth
- `curl` or HTTP client (Postman / Insomnia)
- Optional: Docker (Postgres state store), LangSmith account

### 3.2 Clone / open workspace

Expect sibling packages:

```text
edim/   # or your multi-root workspace
  edim-dde-ai/
  edim-dde-domain/
  edim-dde-api/
```

### 3.3 Create venv and install (from API host)

```bash
cd /path/to/edim/edim-dde-api
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -U pip
pip install -r requirements.txt
pip install -e ".[dev]"

# Domain extras used by live smoke
pip install -e "../edim-dde-domain[azure,databricks,llm]"
pip install -e "../edim-dde-ai[dev]"
```

Confirm imports:

```bash
python -c "import edim_dde_ai, edim_dde_domain, edim_dde_api; print('ok', edim_dde_ai.__version__)"
```

### 3.4 Configure environment

**Option A — shell exports** (session only):

```bash
cp ../edim-dde-domain/.env.example ../edim-dde-domain/.env
# Edit .env with your values — do not commit
set -a && source ../edim-dde-domain/.env && set +a
```

**Option B — export manually** (see checklist §2).

**Auth:**

```bash
az login
az account show   # confirm correct subscription/tenant
```

For SP auth instead of `az login`, set `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` (Foundry; and SQL will also use DefaultAzureCredential chain).

### 3.5 Sanity: unit tests (optional but recommended)

```bash
cd /path/to/edim/edim-dde-domain && pytest -q
cd /path/to/edim/edim-dde-api && pytest -q
```

These use stubs/overrides — they do **not** replace dry/live smoke.

---

## 4. Dry smoke (Foundry yes, Databricks no)

### 4.1 Start API

```bash
cd /path/to/edim/edim-dde-api
source .venv/bin/activate
# Ensure AZURE_OPENAI_* are set; Databricks optional

# Optional: fail fast if Foundry missing
# export EDIM_STRICT_STARTUP=1

uvicorn edim_dde_api.main:app --reload --port 8080
```

Watch logs for `startup_env:` **warnings** (missing warehouse is OK for dry).

### 4.2 Health check

```bash
curl -sS http://127.0.0.1:8080/health | python3 -m json.tool
```

**Pass if:**

- `"status": "ok"`
- `"agents"` includes `cluster_tuning` and `spark_rca`
- process did not crash

OpenAPI: http://127.0.0.1:8080/docs

### 4.3 Dry cluster tuning

```bash
curl -sS http://127.0.0.1:8080/api/v1/recommendations \
  -H 'content-type: application/json' \
  -H 'X-Request-Id: dry-tuning-001' \
  -d '{
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
  }' | python3 -m json.tool
```

**Pass if HTTP 200** and body includes roughly:

- `recommendation` (node family / workers / azure SKU after guardrails)
- `risk_assessment` / `reason_codes`
- `job_cluster_metrics` echoing your override
- **no** warehouse SQL errors in API logs

**Fail patterns:**

| Symptom | Likely cause |
|---------|----------------|
| `503` `FOUNDRY_LLM_NOT_CONFIGURED` | Missing endpoint or `az login` / SP |
| `503` `LLM_CHAIN_ERROR` | Bad deployment name, network, or token scope |
| Slow then timeout | Foundry/firewall; check endpoint from laptop |

### 4.4 Dry Spark RCA

```bash
curl -sS http://127.0.0.1:8080/api/v1/rca/analyze \
  -H 'content-type: application/json' \
  -H 'X-Request-Id: dry-rca-001' \
  -d '{
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
  }' | python3 -m json.tool
```

**Pass if HTTP 200** with `root_cause`, `recommended_actions`, and `status` (typically `completed`).

### 4.5 Optional: LangSmith

If tracing env is set, open the LangSmith project and find runs tagged / named with your `X-Request-Id` or agent id. Absence of traces does not fail dry smoke unless your team requires observability.

---

## 5. Live smoke (Foundry + Databricks SQL)

Prerequisites: §2.1 **and** §2.2 filled; warehouse **running**; your identity can `USE CATALOG` / `SELECT` on the tables.

### 5.1 Verify SQL access outside the API (recommended)

In Databricks SQL editor or `databricks` CLI, run:

```sql
SELECT *
FROM <your DATABRICKS_JOB_CLUSTER_METRICS_TABLE>
LIMIT 5;
```

Pick one row; note `job_id`, `cluster_id` (and `job_run_id` if present).

Confirm columns used by the agent exist (see SELECT in  
`edim-dde-domain/src/edim_dde_domain/agents/cluster_tuning/cluster_tuning.agent.yaml`).  
Missing columns → live SQL errors.

### 5.2 Env for live

```bash
export DATABRICKS_HOST=adb-….azuredatabricks.net
export DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<id>
export DATABRICKS_JOB_CLUSTER_METRICS_TABLE=catalog.schema.job_cluster_metrics
# RCA:
export DATABRICKS_SPARK_METRICS_TABLE=catalog.schema.spark_metrics
export DATABRICKS_SPARK_LOGS_TABLE=catalog.schema.spark_logs

export AZURE_OPENAI_ENDPOINT=https://….openai.azure.com
export AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o

# Optional fail-fast:
export EDIM_STRICT_STARTUP=1
export EDIM_REQUIRE_SQL=1

az login
```

Restart uvicorn (§4.1).

### 5.3 Live cluster tuning (no metrics override)

```bash
curl -sS http://127.0.0.1:8080/api/v1/recommendations \
  -H 'content-type: application/json' \
  -H 'X-Request-Id: live-tuning-001' \
  -d '{
    "job_id": "<real-job-id>",
    "cluster_id": "<real-cluster-id>",
    "include_explanation": false
  }' | python3 -m json.tool
```

**Pass if HTTP 200**, `job_cluster_metrics` populated from UC (not empty stub), recommendation present.

**Fail patterns:**

| Symptom | Likely cause |
|---------|----------------|
| Databricks not configured | Host/path unset or auth failed |
| No job metrics | Wrong ids / empty table / date filters |
| SQL column errors | Schema drift vs YAML SELECT |
| Token errors | Re-run `az login`; Apps need forwarded user token |

### 5.4 Live RCA

Provide a real `job_run_id` (and optional `job_id` / `job_run_date`) **without** `evidence_pack` so SQL collect runs:

```bash
curl -sS http://127.0.0.1:8080/api/v1/rca/analyze \
  -H 'content-type: application/json' \
  -H 'X-Request-Id: live-rca-001' \
  -d '{
    "job_run_id": "<real-job-run-id>",
    "job_id": "<real-job-id>",
    "job_run_date": "YYYY-MM-DD"
  }' | python3 -m json.tool
```

**Pass if** evidence-backed `root_cause` and actions; logs show SQL sections succeeding (or intentional empties handled by agent).

---

## 6. Remote / shared environment smoke

Prefer the full host guide: [Deploy & hosting (Databricks Apps / Docker / ACA)](../api/deploy-and-hosting.md).

Use the same curls against a **deployed** base URL instead of `localhost`.

| Step | Action |
|------|--------|
| 1 | Get base URL from team (e.g. Databricks App) — `https://…` |
| 2 | Confirm network (VPN / private link) if required |
| 3 | `curl -sS "$BASE/health"` |
| 4 | Dry or live POSTs to `$BASE/api/v1/recommendations` and `/rca/analyze` |
| 5 | **Apps SQL auth:** browser/gateway must send `X-Forwarded-Access-Token`; local `az login` does **not** apply on the server for user-scoped SQL |
| 6 | **Foundry on server:** SP secrets from Key Vault / env — not your laptop `az login` |

Example:

```bash
export BASE=https://your-edim-api.example.com
curl -sS "$BASE/health" | python3 -m json.tool
# then same JSON bodies as §4–5 with "$BASE/api/v1/..."
```

Record: URL, request ids, HTTP status, whether dry or live, who ran it, date.

---

## 7. Pass / fail summary checklist

Print and tick:

- [ ] Install + import OK  
- [ ] `az login` (or SP) OK  
- [ ] Foundry endpoint + deployment set  
- [ ] `/health` → `ok` + both agents  
- [ ] **Dry** tuning → 200 + recommendation  
- [ ] **Dry** RCA → 200 + root_cause  
- [ ] *(Live)* SQL probe in warehouse OK  
- [ ] *(Live)* tuning without `metrics` → 200 + UC metrics  
- [ ] *(Live)* RCA without `evidence_pack` → 200  
- [ ] *(Optional)* LangSmith run visible  
- [ ] *(Remote)* health + one dry call on shared URL  

---

## 8. Troubleshooting quick reference

| Problem | Check |
|---------|--------|
| Port in use | Change `--port` or kill old uvicorn |
| Editable install wrong package | `pip show edim-dde-domain` → path under your workspace |
| `.env` not loaded | Export explicitly or `set -a; source …/.env; set +a` from shell that starts uvicorn |
| 503 Foundry | Endpoint, deployment name, `az account show`, firewall |
| SQL auth local | `az login` + warehouse allows your AAD user |
| SQL auth Apps | Forwarded access token present on request |
| Schema / FQN reject | Table name chars; use `catalog.schema.table` |
| Startup refused | `EDIM_STRICT_STARTUP` — fix Foundry env or unset flag for dry laptop work |

---

## 9. What to send the team when blocked

1. Mode: dry / live / remote  
2. `curl /health` JSON  
3. Request id (`X-Request-Id`)  
4. HTTP status + truncated error body (`error_code` if any)  
5. Whether `metrics` / `evidence_pack` were used  
6. **Redact** secrets; share endpoint **host** only if needed  

When sharing UC/Foundry details for a joint live smoke, prefer a **private** channel and a filled §2 checklist — never paste client secrets into tickets or git.

---

## Next

- [Configuration](../api/configuration.md) · [Env vars](../reference/env-vars.md)  
- [Sources and SQL](../domain/sources-and-sql.md) — overrides vs live collect  
- Product P0 in [BACKLOG.md](../../../BACKLOG.md)
