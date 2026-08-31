# Self-hosted LangSmith setup guide (SDBX / DEV / PROD)

**Learning path:** C5 · [Preface](../README.md)  
**← Previous:** [Observability](observability.md) · **Next:** [State store](state-store.md) →

## Chapter summary

Hands-on self-hosted LangSmith configuration for EDIM across SDBX / DEV /
PROD: projects, env vars, tracing validation, and the distinction between
using LangSmith as a tracing destination and operating the full LangSmith
platform. LangSmith Cloud is not an EDIM deployment target.

**Outcome:** you can produce a visible trace from a dry agent call and find it by `X-Request-Id`.

---

Hands-on guide: configure the enterprise LangSmith instance for EDIM, validate
traces from a Windows or Linux laptop, and understand how this differs from
generic LangSmith UI quickstarts.

**R1 scope:** tracing + one **tracing project** per EDIM env.  
**Later:** datasets, evaluators, CI quality gates (backlog BL-029 / BL-033).

---

## 1. What LangSmith is

[LangSmith](https://smith.langchain.com/) is LangChain’s observability product:

| Capability | R1 use |
|------------|--------|
| **Tracing** | See LangGraph runs, LLM spans, latency, tokens, errors |
| **Debugging** | Open a failed run; inspect inputs/outputs |
| **Evaluation** | Golden datasets + scorers — **later** |

Observability is a **side channel**: traces must not block `/health` or agent responses. See [Observability providers](observability.md).

---

## 2. How EDIM integrates (not the UI “OpenAI Agents SDK” sample)

LangSmith’s project UI shows many **integration quickstarts** (OpenAI Agents SDK, etc.). Those samples use **direct SDK wiring** — for example `pip install langsmith[openai-agents]` and `OpenAIAgentsTracingProcessor`.

**EDIM does not use that path.** We use **LangGraph + langchain-core automatic tracing**:

```text
HTTP POST /api/v1/…
        │
        ▼
edim-dde-api
  configure_observability_from_env()     # EDIM_OBSERVABILITY
  build_run_config(agent_id, request_id)
        │
        ▼
MetadataAgent.invoke(state, config=…)
  ObservabilityProvider.merge_invoke_kwargs()
  tags: agent_id, env:dev, request_id, obs:langsmith
        │
        ▼
LangGraph (from *.agent.yaml)
  LangChain callbacks (built into langchain-core)
        │
        ▼
langsmith client  →  LangSmith API  →  Runs in LANGCHAIN_PROJECT
```

| Layer | EDIM | LangSmith UI “OpenAI Agents SDK” sample |
|-------|------|----------------------------------------|
| Orchestration | LangGraph from YAML | OpenAI Agents SDK |
| Tracing hook | Env + LangChain callbacks | Manual processor import |
| Env vars | `LANGCHAIN_TRACING_V2` + `LANGCHAIN_*` | `LANGSMITH_TRACING` + `LANGSMITH_*` |
| Extra pip | None required (see §4) | `langsmith[openai-agents]` |

Same **Runs** UI — different **path into** LangSmith. Ignore the OpenAI Agents quickstart unless you build a separate app on that SDK.

---

## 3. Packages — why `langsmith` is not in `requirements.txt`

Runtime deps for `edim-dde-ai` are `langgraph`, `langchain-core`, and `PyYAML`. Tracing does **not** need a separate app install:

```text
edim-dde-ai
  └── langgraph
        └── langchain-core
              └── langsmith    ← installed transitively
```

Optional explicit pin (CI / upgrades):

```bash
pip install 'edim-dde-ai[observability]'
# equivalent: pip install 'langsmith>=0.1'
```

Product agents in `edim-dde-domain` **do not** import LangSmith — tracing stays in the framework + API host.

---

## 4. Environment variables — `LANGCHAIN_*` vs `LANGSMITH_*`

### 4.1 What EDIM documents (source of truth)

| Variable | Required | Purpose |
|----------|----------|---------|
| `EDIM_OBSERVABILITY` | Recommended | `langsmith` \| `mlflow` \| `none` \| `auto` (default `auto`) |
| `EDIM_ENV` | Yes | Tags traces (`env:dev`); separate from LangSmith project name |
| `LANGCHAIN_TRACING_V2` | **Yes for tracing** | Turns on **LangGraph / LangChain** v2 tracing to LangSmith |
| `LANGCHAIN_API_KEY` | Yes | API key from LangSmith Settings |
| `LANGCHAIN_PROJECT` | Yes | **Tracing project** name (where runs appear) |
| `LANGCHAIN_ENDPOINT` | Self-hosted | API base URL (SaaS default: `https://api.smith.langchain.com`) |
| `EDIM_LANGSMITH_ENABLED` | Optional | **Off switch only** — set `false` to force EDIM to ignore tracing env |

Example (DEV, self-hosted):

```bash
EDIM_ENV=dev
EDIM_OBSERVABILITY=langsmith

LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=edim-dde-dev
LANGCHAIN_ENDPOINT=https://<self-hosted-langsmith-api>/api/v1
```

Example (self-hosted):

```bash
LANGCHAIN_ENDPOINT=https://your-langsmith-host.example.net/api/v1
LANGCHAIN_PROJECT=edim-dde-ai-sdbx
```

Use the **API** URL your platform team provides (often ends in `/api/v1`). The browser UI URL may differ.

### 4.2 Why not `LANGSMITH_TRACING` / `LANGSMITH_TRACING_V2`?

| Name | Who uses it |
|------|-------------|
| `LANGCHAIN_TRACING` | Legacy LangChain v1 tracer — **not** LangSmith v2 |
| `LANGCHAIN_TRACING_V2` | **LangGraph / LangChain** → LangSmith (what EDIM uses) |
| `LANGSMITH_TRACING` | Newer **LangSmith SDK-first** apps (UI quickstarts) |
| `LANGSMITH_TRACING_V2` | **Not a standard name** — do not use |

EDIM’s `tracing_enabled()` checks **`LANGCHAIN_TRACING_V2`**, not `LANGSMITH_TRACING`. Do not replace V2 with `LANGSMITH_TRACING` alone without verifying traces still appear.

Many LangSmith / LangChain versions also accept **`LANGSMITH_*` aliases** for key, project, and endpoint. You may set both prefixes in `.env` if your ops team standardizes on `LANGSMITH_*`, but keep **`LANGCHAIN_TRACING_V2=true`** for EDIM.

| LangSmith UI / newer docs | EDIM / LangGraph (keep these) |
|-----------------------------|-------------------------------|
| `LANGSMITH_TRACING=true` | **`LANGCHAIN_TRACING_V2=true`** |
| `LANGSMITH_API_KEY` | `LANGCHAIN_API_KEY` (or both) |
| `LANGSMITH_PROJECT` | `LANGCHAIN_PROJECT` (or both) |
| `LANGSMITH_ENDPOINT` | `LANGCHAIN_ENDPOINT` (or both) |

Full catalog: [Environment variables](../reference/env-vars.md#langsmith-tracing).

### 4.3 `EDIM_OBSERVABILITY` vs `LANGCHAIN_TRACING_V2`

Two layers:

```text
LANGCHAIN_TRACING_V2=true     →  LangGraph sends spans to LangSmith
EDIM_OBSERVABILITY=langsmith  →  EDIM picks LangSmith provider + merges tags
EDIM_LANGSMITH_ENABLED=false  →  EDIM kill switch (auto mode treats as off)
```

| Goal | Set |
|------|-----|
| Tracing on | `LANGCHAIN_TRACING_V2=true` + key + project + `EDIM_OBSERVABILITY=langsmith` (or `auto`) |
| Tracing off | unset `LANGCHAIN_TRACING_V2`, or `EDIM_OBSERVABILITY=none`, or `EDIM_LANGSMITH_ENABLED=false` |

**Do not** set `EDIM_LANGSMITH_ENABLED=auto` — valid values are **unset** or **`false`** only.

### 4.4 Loading `.env` (API does not auto-load)

`uvicorn` does **not** read `edim-dde-domain/.env` by itself. Export vars in the **same shell** that starts the API.

**Linux / Git Bash:**

```bash
set -a && source ../edim-dde-domain/.env && set +a
python -m uvicorn edim_dde_api.main:app --host 127.0.0.1 --port 8080
```

**Windows PowerShell:**

```powershell
Get-Content C:\path\to\edim\edim-dde-domain\.env | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $k, $v = $_ -split '=', 2
  [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim().Trim('"'), 'Process')
}
python -m uvicorn edim_dde_api.main:app --host 127.0.0.1 --port 8080
```

Or use `make host-run` from `edim-dde-api` (Git Bash) which sources `../edim-dde-domain/.env`.

PROD: load `LANGCHAIN_API_KEY` from Key Vault — default map key `langchain-api-key` → `LANGCHAIN_API_KEY`. See [Key Vault bootstrap](key-vault-bootstrap.md).

---

## 5. LangSmith UI — workspaces, applications, tracing projects

Do not confuse LangSmith **UI folders** with EDIM **`EDIM_ENV`** or Databricks workspaces.

```text
Organization
    └── Workspace          ← RBAC boundary (picker: bottom-left / Settings)
            └── Application   ← UI folder (sidebar dropdown)
                    └── Tracing project   ← LANGCHAIN_PROJECT (Runs tab)
```

| UI concept | EDIM equivalent | Notes |
|------------|-----------------|-------|
| **Workspace** | Not `EDIM_ENV` | LangSmith team isolation; optional extra workspaces need org admin |
| **Application** (e.g. *My First App*) | None | UI-only grouping; use **My First App**, not **All Applications**, to see projects |
| **Tracing project** | `LANGCHAIN_PROJECT` | `edim-dde-dev`, `edim-dde-ai-sdbx`, etc. |
| **`EDIM_ENV`** | Tag `env:dev` on traces | Process env name; does not auto-create LangSmith projects |

**All Applications** is a filter across the workspace — it often **hides** the project list. Select **My First App** (or your app) to see **Tracing / Projects**.

You usually **do not** need a second LangSmith workspace per EDIM env. Use **separate tracing projects** (`edim-dde-sdbx`, `edim-dde-dev`, `edim-dde-prod`).

### 5.1 UI setup (once per LangSmith instance)

1. Sign in (SaaS or self-hosted).
2. **Settings → API Keys** → create key → put in `.env` or Key Vault.
3. Sidebar **Application** → **My First App** (default is fine).
4. **Tracing → Projects** — note or create project names matching `LANGCHAIN_PROJECT`.
5. Projects are **auto-created** on first trace if missing — manual create is optional.

Suggested project names:

| EDIM env (`EDIM_ENV`) | Suggested `LANGCHAIN_PROJECT` |
|-----------------------|-------------------------------|
| `sdbx` | `edim-dde-sdbx` |
| `dev` | `edim-dde-dev` |
| `prod` | `edim-dde-prod` |

---

## 6. Self-hosted deployment versus tracing

| Option | EDIM status | When |
|--------|-------------|------|
| **LangSmith Cloud** | Not approved | Do not send EDIM production or development traces to SaaS |
| **Self-hosted tracing endpoint** | Supported | ACA Native, local, or another EDIM host sends traces to the private LangSmith API |
| **Full self-hosted LangSmith Deployment on AKS** | Optional | The platform team operates the LangSmith UI/control plane and Agent Server inside Azure |

Self-hosted endpoint example:

```bash
LANGCHAIN_ENDPOINT=https://<self-hosted-langsmith-api>/api/v1
```

Ensure the API process can reach that private host through VNet, private DNS,
or approved VPN/firewall routes. The API key must be issued from that
self-hosted instance, not from SaaS.

Full platform installation: [Deployment targets](../api/deployment-targets.md) §6.
The platform team must use the vendor’s version-matched installation
instructions, license process, Helm values, backing-service requirements,
backup policy, and upgrade procedure:
[Self-host LangSmith](https://docs.langchain.com/langsmith/self-hosted).

The application team does not install or upgrade the AKS control plane as part
of an EDIM graph release. It supplies the versioned graph package and validates
the Agent Server import or tracing path.

---

## 7. Validate tracing (step-by-step)

### 7.1 Confirm process config

```bash
curl -sS http://127.0.0.1:8080/health
```

Pass: `"observability": "langsmith"`. If `"none"`, `.env` was not loaded or tracing env is off.

### 7.2 Send one correlated request (dry — no Databricks SQL)

Foundry must be configured. Metrics in the body skip SQL but still run the sizing LLM.

```bash
curl -sS -D - http://127.0.0.1:8080/api/v1/cluster_tuning/recommend \
  -H 'content-type: application/json' \
  -H 'X-Request-Id: langsmith-dev-001' \
  -d '{
    "job_id": "ls-dev-check",
    "cluster_id": "ls-dev-check",
    "include_explanation": false,
    "metrics": {
      "azure_worker_vm_size": "Standard_D8s_v5",
      "max_worker_nodes_provisioned": 16,
      "avg_worker_nodes_consumed": 4.0,
      "peak_worker_cpu_utilization_pct": 22,
      "peak_worker_memory_utilization_pct": 31,
      "avg_worker_cpu_utilization_pct": 20,
      "avg_worker_memory_utilization_pct": 25
    }
  }'
```

Pass: HTTP 200 (or Foundry error — trace may still appear); response header `X-Request-Id: langsmith-dev-001`.

Wait 10–30 seconds.

### 7.3 Find the run in LangSmith

1. Application → **My First App**
2. Project → name from **`LANGCHAIN_PROJECT`** (not `EDIM_ENV`)
3. **Tracing / Runs** — newest run named **`cluster_tuning`**
4. Tags: `agent_id:cluster_tuning`, `env:dev`, `obs:langsmith`
5. Metadata: `request_id` = `langsmith-dev-001`

Optional RCA dry call: `POST /api/v1/rca/analyze` with `evidence_pack` override and `X-Request-Id: langsmith-dev-rca-001` → run name **`spark_rca`**.

Windows checklist: [Windows smoke § LangSmith](../contribute/windows-smoke-checklist.md#step-6b--validate-langsmith-optional).

---

## 8. What to look for (ops checklist)

| Question | Where in LangSmith |
|----------|--------------------|
| Did the run fail? | Run status / error |
| Which model? | LLM child span metadata |
| Token count / latency? | LLM span metrics |
| Match API call? | Metadata `request_id` = `X-Request-Id` |
| Match deploy env? | Tag `env:dev` (from `EDIM_ENV`) |

Also check API logs: `[request_id=…]` on the same id.

---

## 9. PII and compliance caution

Traces may include prompt text. EDIM redacts some patterns in **API logs**; LangSmith spans may still contain LLM I/O unless you redact before invoke. See [PII guardrails](pii-guardrails.md). Use non-prod projects for experiments.

---

## 10. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `/health` → `"observability": "none"` | Load `.env` in uvicorn shell; set `EDIM_OBSERVABILITY=langsmith` or `auto` + `LANGCHAIN_TRACING_V2=true` |
| No runs | Wrong API key; wrong endpoint; VPN; project name mismatch |
| Runs in wrong project | `LANGCHAIN_PROJECT` must match UI project exactly |
| Cannot find projects in UI | Select **My First App**, not **All Applications** |
| 401 from LangSmith | Key from different instance (SaaS key vs self-hosted) |
| Used `LANGSMITH_TRACING` only | Add **`LANGCHAIN_TRACING_V2=true`** for LangGraph |
| `EDIM_LANGSMITH_ENABLED=auto` | Remove line — only `false` or unset is valid |
| Local works, Apps empty | Apps env / Key Vault missing `LANGCHAIN_*`; outbound HTTPS |
| OpenAI Agents sample does not apply | Expected — EDIM uses LangGraph auto-tracing (§2) |

---

## 11. Maturity — what is wired vs later

| Capability | Status |
|------------|--------|
| LangSmith provider + tags (`agent_id`, `request_id`, `edim_env`) | **Done** |
| `/health` reports `observability` | **Done** |
| Trace PII scrubbing in LangSmith payloads | **Partial** — logs only; spans may contain prompts |
| Datasets / LLM judges / CI eval gates | **Later** (BL-033+) |
| Operationalized DEV/PROD proof on shared Apps | **Per deploy** — validate with §7 |

---

## 12. Next (later)

- Upload golden datasets for `cluster_tuning` / `spark_rca`
- Wire quality harness scores to LangSmith evaluators
- Dashboard / alerts (BL-030)

---

## Related

- [Observability providers](observability.md)
- [Environment variables § LangSmith](../reference/env-vars.md#langsmith-tracing)
- [Windows smoke checklist](../contribute/windows-smoke-checklist.md)
- [Config → observability flow](../architecture/config-to-observability.md)
- [Environments](environments.md)

## Summary

- One tracing project per `EDIM_ENV`; datasets/evaluators are later backlog.
- Validate with `/health` observability field and a dry recommend/analyze call.

**Next →** [State store (C6)](state-store.md)

<!-- edim-learning-nav -->
---

← [Observability](observability.md) · [Preface](../README.md) · [State store](state-store.md) →
