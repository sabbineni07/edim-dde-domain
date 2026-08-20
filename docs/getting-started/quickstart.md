# Quickstart (A1)

**Learning path:** A1 · [Home](../README.md)  
**← Previous:** [Guide map](guide-map.md) · **Next:** [Core concepts](concepts.md) →

## Chapter summary

This chapter walks through a **minimal working EDIM DDE stack** on your machine. You will either run offline unit tests (no Foundry) or start the API and invoke bundled agents over HTTP with request-body overrides that skip Databricks SQL.

**Time:** 15–30 minutes · **Outcome:** confirmed install and one successful agent invocation.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.10+ | Match `requires-python` in package `pyproject.toml` files |
| Sibling repos | `edim-dde-ai`, `edim-dde-domain`, `edim-dde-api` under a common parent |
| (Path B only) Azure OpenAI / Foundry | Endpoint, deployment, and credentials — see [Configuration (G1)](../api/configuration.md) |

---

## Choose a path

| Path | Databricks SQL | Foundry LLM | Use when |
|------|----------------|-------------|----------|
| **A — Pytest (offline)** | Bypassed via test overrides | Stubbed (`DomainStubLLM`) | CI, local sanity, no cloud credentials |
| **B — Live HTTP** | Optional (request overrides) | **Required** | Demo, integration smoke, real LLM output |

!!! warning "LLM behavior with overrides"
    Request fields `metrics` and `evidence_pack` bypass **warehouse SQL only**. Bundled agents still execute **`llm_chain`** nodes (tuning sizing; RCA synthesis). Setting `include_explanation: false` skips the *explanation* LLM call — not sizing or synthesis.

---

## Step 1 — Install packages

From the API repository (editable install pulls siblings via `requirements.txt`):

```bash
cd edim-dde-api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
```

Optional explicit sibling installs:

```bash
cd ../edim-dde-domain && pip install -e ".[dev]"
cd ../edim-dde-ai && pip install -e ".[dev]"
```

---

## Path A — Offline validation (pytest)

Tests register `edim_dde_domain.testing.DomainStubLLM` and supply SQL overrides. **This is the supported path without Foundry.**

```bash
cd edim-dde-domain && pytest -q
cd ../edim-dde-api && pytest -q
cd ../edim-dde-ai && pytest -q
```

!!! note
    Running `uvicorn` directly does **not** use the test stub. Path B configures Foundry via API lifespan.

---

## Path B — Live HTTP

### Step 2 — Configure Foundry

```bash
az login
export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
export AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
# Or: EDIM_FOUNDRY_TENANT_ID, EDIM_FOUNDRY_CLIENT_ID, EDIM_FOUNDRY_CLIENT_SECRET
```

Full variable list: [Configuration (G1)](../api/configuration.md) · [Environment variables (H1)](../reference/env-vars.md).

Warehouse variables are **optional** when using SQL bypass overrides below.

### Step 3 — Optional planes

```bash
export EDIM_ENV=dev
export EDIM_OBSERVABILITY=langsmith
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=lsv2_pt_...
export LANGCHAIN_PROJECT=edim-dde-dev
```

| Plane | Example | Chapter |
|-------|---------|---------|
| State store | `EDIM_STATE_STORE=postgres` | [State store (C6)](../platform/state-store.md) |
| Retrieval | `EDIM_RETRIEVAL=faiss` | [Retrieval (C7)](../platform/retrieval-and-rag.md) |

On Windows, load `.env` into the same PowerShell session before starting uvicorn — [Windows smoke (H5b)](../contribute/windows-smoke-checklist.md).

### Step 4 — Start the API

```bash
cd edim-dde-api
source .venv/bin/activate
uvicorn edim_dde_api.main:app --reload --port 8080
```

**Lifespan order:** Key Vault → observability → state store → recommendation store → retrieval → `bootstrap_agents()` → catalog sync → lazy Foundry provider.

```bash
curl -s localhost:8080/health | python3 -m json.tool
```

Expected: `"status": "ok"` and registered agent ids. Without Foundry configuration, agent routes return **503** `FOUNDRY_LLM_NOT_CONFIGURED`.

### Step 5 — Invoke cluster tuning (SQL bypass)

```bash
curl -s localhost:8080/api/v1/cluster_tuning/recommend \
  -H 'content-type: application/json' \
  -H 'X-Request-Id: demo-tuning-1' \
  -d '{
    "job_id": "j-1",
    "cluster_id": "c-1",
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
  }'
```

### Step 6 — Invoke Spark RCA (SQL bypass)

```bash
curl -s localhost:8080/api/v1/rca/analyze \
  -H 'content-type: application/json' \
  -H 'X-Request-Id: demo-rca-1' \
  -d '{
    "job_run_id": "jr-1",
    "job_id": "j-1",
    "evidence_pack": {
      "job_run_id": "jr-1",
      "evidence": [{"ref": "e1", "excerpt": "Executor OutOfMemoryError: Java heap space"}],
      "raw_anchors": {"failure_reason": "Executor OutOfMemoryError: Java heap space"}
    }
  }'
```

With retrieval enabled, RCA runs `rag.retrieve` before synthesis — [Retrieval (C7)](../platform/retrieval-and-rag.md).

---

## What you exercised

```text
HTTP → FastAPI → create_agent(id).invoke(state)
                      │
                      ├─ RequestId middleware
                      ├─ ObservabilityProvider (optional)
                      ├─ StateStore (catalog at startup)
                      └─ LangGraph YAML nodes → OpenAPI DTO
```

Browse the full guide at `http://127.0.0.1:8080/guide/` after `make guide-site && make compose-up` from `edim-dde-api`.

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| **503** `FOUNDRY_LLM_NOT_CONFIGURED` | Missing Foundry env | Set `AZURE_OPENAI_*` or `EDIM_FOUNDRY_*`; see G1 |
| **502** domain/SQL errors | Live SQL without warehouse auth | Use overrides (above) or configure Databricks — B7 |
| Empty agents in `/health` | Bootstrap failure | Check startup logs; verify sibling packages installed |
| Tests pass, curl fails | Tests use stub; uvicorn uses Foundry | Expected — complete Path B config |

---

## Summary

- **Path A** validates packages without cloud LLM credentials.
- **Path B** proves the HTTP host and bundled agents with Foundry.
- Next, learn the vocabulary in **[Core concepts (A2)](concepts.md)**, then **[Part B — Architecture](../architecture/index.md)**.

!!! tip "Extended validation"
    Follow [Live smoke test (H5)](../contribute/live-smoke-test.md) for dry/live suites beyond this quickstart.

← [Guide map](guide-map.md) · [Core concepts (A2)](concepts.md) →
