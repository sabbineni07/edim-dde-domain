# Quickstart

Goal: run the API locally and invoke a bundled agent with **offline overrides** (no live Databricks/Foundry required for this path).

## Prerequisites

- Python 3.10+
- Parent workspace: `edim/` containing `edim-dde-ai`, `edim-dde-domain`, `edim-dde-api`

## 1. Install (editable siblings)

```bash
cd /Users/sabbineni/projects/edim/edim-dde-api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
# Ensures editable edim-dde-ai + edim-dde-domain from sibling paths
```

Install domain/ai the same way if you develop them in isolation:

```bash
cd ../edim-dde-domain && pip install -e ".[dev]"
cd ../edim-dde-ai && pip install -e ".[dev]"
```

## 2. Run tests (sanity)

```bash
cd /Users/sabbineni/projects/edim/edim-dde-domain && pytest -q
cd /Users/sabbineni/projects/edim/edim-dde-api && pytest -q
```

## 3. Start the API

```bash
cd /Users/sabbineni/projects/edim/edim-dde-api
source .venv/bin/activate
uvicorn edim_dde_api.main:app --reload --port 8080
```

Lifespan calls `bootstrap_agents()` (bundled YAML + nodes) and installs a lazy Foundry LLM provider.

```bash
curl -s localhost:8080/health
# {"status":"ok","agents":["cluster_tuning","spark_rca",...]}
```

## 4. Call cluster tuning (metrics override)

Without Databricks, pass `metrics` in the body so `domain.sql.query` is skipped:

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

> **Note:** Live LLM calls need Foundry env + `az login` (or SP). API tests use `edim_dde_domain.testing.DomainStubLLM`. For a live HTTP demo with LLM, set env from [configuration](../api/configuration.md) or run unit/e2e tests with the stub.

## 5. Call Spark RCA (evidence_pack override)

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

## Next

- [Concepts](concepts.md)
- [Live E2E](../api/configuration.md) (warehouse + Foundry)
- [Build a new agent](../build-agents/step-by-step.md)
