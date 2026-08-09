# Quickstart (A1)

**Learning path:** A1 · [Guide home](../README.md)  
**← Previous:** [Guide home](../README.md) · **Next:** [Core concepts](concepts.md) →

Get a working stack on your laptop in two paths: offline tests, or live HTTP with Foundry.

After Compose is up, browse the full guide at `http://127.0.0.1:8080/guide/` (`make guide-site` then `make compose-up` from `edim-dde-api`).

---

## Two paths

| Path | Skips Databricks? | Skips Foundry? | Use when |
|------|-------------------|----------------|----------|
| **A. Pytest + `DomainStubLLM`** | Yes (with overrides) | Yes (stub) | Local sanity / CI |
| **B. Live HTTP (`uvicorn` + curl)** | Yes (with overrides) | **No** — needs Foundry | Demo / E2E against real LLM |

`metrics` / `evidence_pack` in the request body only bypass **SQL warehouse** reads. Both bundled agents still run **`llm_chain`** (sizing for tuning; synthesize for RCA). `include_explanation: false` skips the *explanation* LLM only — not sizing.

---

## Prerequisites

- Python 3.10+
- Sibling packages under `edim/`: `edim-dde-ai`, `edim-dde-domain`, `edim-dde-api`

---

## 1. Install (editable siblings)

```bash
cd edim-dde-api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
```

Optional isolation installs:

```bash
cd ../edim-dde-domain && pip install -e ".[dev]"
cd ../edim-dde-ai && pip install -e ".[dev]"
```

---

## Path A — Offline (tests)

Tests install `edim_dde_domain.testing.DomainStubLLM` and pass SQL overrides. **This is the supported no-Foundry path.**

```bash
cd edim-dde-domain && pytest -q
cd ../edim-dde-api && pytest -q
cd ../edim-dde-ai && pytest -q
```

Plain `uvicorn` does **not** use the stub; its lifespan installs Foundry (see Path B).

---

## Path B — Live HTTP

### Foundry (required for curl)

```bash
az login   # or set EDIM_FOUNDRY_TENANT_ID / EDIM_FOUNDRY_CLIENT_ID / EDIM_FOUNDRY_CLIENT_SECRET
export AZURE_OPENAI_ENDPOINT=https://….openai.azure.com
export AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

Full list: [configuration](../api/configuration.md) · [env vars](../reference/env-vars.md).

Databricks warehouse env is **optional** if you pass `metrics` / `evidence_pack` overrides below.

### Optional planes (recommended as you grow)

```bash
export EDIM_ENV=dev

# Observability
export EDIM_OBSERVABILITY=langsmith
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=lsv2_pt_...
export LANGCHAIN_PROJECT=edim-dde-dev

# Control plane (optional locally)
# export EDIM_STATE_STORE=postgres
# export EDIM_DATABASE_URL=postgresql://edim:edim@localhost:5432/edim

# Retrieval for spark_rca runbooks (optional)
# pip install 'edim-dde-ai[faiss]'
# export EDIM_RETRIEVAL=faiss
# export EDIM_FAISS_INDEX_PATH=/tmp/edim-indexes
```

### Start API

```bash
cd edim-dde-api
source .venv/bin/activate
uvicorn edim_dde_api.main:app --reload --port 8080
```

**Lifespan (in order):** Key Vault → observability → state store → retrieval → `bootstrap_agents()` → catalog sync → lazy Foundry.

```bash
curl -s localhost:8080/health
# includes: agents, version, observability, state_store, retrieval
```

Without Foundry env/auth, agent curls return **503** `FOUNDRY_LLM_NOT_CONFIGURED`.

### Cluster tuning (`metrics` override — skip SQL)

```bash
curl -s localhost:8080/api/v1/recommendations \
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

### Spark RCA (`evidence_pack` override — skip SQL)

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

With `EDIM_RETRIEVAL=faiss` and an indexed corpus, RCA also runs `rag.retrieve` for runbook grounding before the LLM.

---

## What you just exercised

```text
curl → FastAPI → create_agent().invoke → LangGraph YAML nodes → DTO response
                      │
                      ├─ ObservabilityProvider (optional traces)
                      ├─ StateStore (catalog already synced at startup)
                      └─ RetrievalProvider (spark_rca only, if enabled)
```

---

## Next in the learning path

→ **[A2 — Core concepts](concepts.md)** (required next)  
Then **[B1 — End-to-end design](../architecture/end-to-end-design.md)** for architecture depth.

**Proving the stack with Foundry / SQL:** [Live & dry smoke test](../contribute/live-smoke-test.md)

[Guide home](../README.md)
