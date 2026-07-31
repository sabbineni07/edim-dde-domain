# Quickstart

Two paths:

| Path | Skips Databricks? | Skips Foundry? | Use when |
|------|-------------------|----------------|----------|
| **A. Pytest + `DomainStubLLM`** | Yes (with overrides) | Yes (stub) | Local sanity / CI |
| **B. Live HTTP (`uvicorn` + curl)** | Yes (with overrides) | **No** — needs Foundry | Demo / E2E against real LLM |

`metrics` / `evidence_pack` in the request body only bypass **SQL warehouse** reads. Both bundled agents still run **`llm_chain`** (sizing for tuning; synthesize for RCA). `include_explanation: false` skips the *explanation* LLM only — not sizing.

## Prerequisites

- Python 3.10+
- Sibling packages under `edim/`: `edim-dde-ai`, `edim-dde-domain`, `edim-dde-api`

## 1. Install (editable siblings)

```bash
cd /Users/sabbineni/projects/edim/edim-dde-api
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
cd /Users/sabbineni/projects/edim/edim-dde-domain && pytest -q
cd /Users/sabbineni/projects/edim/edim-dde-api && pytest -q
```

Plain `uvicorn` does **not** use the stub; its lifespan installs Foundry (see Path B).

---

## Path B — Live HTTP

### Foundry (required for curl)

```bash
az login   # or set AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET
export AZURE_OPENAI_ENDPOINT=https://….openai.azure.com
export AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

Full list: [configuration](../api/configuration.md) · [env vars](../reference/env-vars.md).

Databricks warehouse env is **optional** if you pass `metrics` / `evidence_pack` overrides below.

### Start API

```bash
cd /Users/sabbineni/projects/edim/edim-dde-api
source .venv/bin/activate
uvicorn edim_dde_api.main:app --reload --port 8080
```

Lifespan: `bootstrap_agents()` + lazy Foundry provider (constructs the real client on **first** `llm_chain` call so `/health` works before LLM env is set).

```bash
curl -s localhost:8080/health
# {"status":"ok","agents":["cluster_tuning","spark_rca",...]}
```

Without Foundry env/auth, agent curls return **503** `FOUNDRY_LLM_NOT_CONFIGURED`.

### Cluster tuning (`metrics` override — skip SQL)

```bash
curl -s localhost:8080/api/v1/recommendations \
  -H 'content-type: application/json' \
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

Still invokes the **sizing** `llm_chain`. Set `"include_explanation": true` only if you also want the second (explanation) LLM call.

### Spark RCA (`evidence_pack` override — skip SQL)

```bash
curl -s localhost:8080/api/v1/rca/analyze \
  -H 'content-type: application/json' \
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

Still invokes the **rca** `llm_chain` after rule classify.

---

## Next

- [Concepts](concepts.md) — agents, state, overrides
- [Sources and SQL](../domain/sources-and-sql.md) — `skip_if_key`, overrides
- [Live warehouse + Foundry](../api/configuration.md)
- [Build a new agent](../build-agents/step-by-step.md)
