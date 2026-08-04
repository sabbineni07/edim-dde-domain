# Bundled agents (E3)

**Learning path:** E3 · [Guide home](../README.md)  
**← Previous:** [SQL design deep dive](../DESIGN_SOURCES_AND_SQL_NODES.md) · **Next:** [Agent package layout](../build-agents/agent-package-layout.md) →

Shipped inside `edim-dde-domain` under `agents/`. Both follow [agent package layout](../build-agents/agent-package-layout.md) (`helpers/`, `content/`).

---

## Overview

| `agent_id` | Purpose | Highlights |
|------------|---------|------------|
| `cluster_tuning` | Job cluster sizing recommendations | SQL metrics → sizing LLM → guardrails → resource optimization % |
| `spark_rca` | Spark job root-cause analysis | SQL telemetry → evidence → classify → **runbook retrieve (RAG)** → RCA LLM |

---

## `cluster_tuning` flow

```text
domain.sql.query (metrics)
  → domain.tuning.* (feature / sizing / guardrails / risk)
  → llm_chain (sizing, optional explanation)
  → API projects TuningResponse
```

- **Override:** pass `metrics` in the request to skip SQL.
- **No retrieval plane** in R1 (structured UC metrics dominate).

---

## `spark_rca` flow (RAG pilot)

```text
domain.sql.query × N (anchors, plans, logs, timeline, stages)
  → domain.rca.assemble_evidence
  → domain.rca.classify_failure
  → domain.rca.build_retrieval_query
  → rag.retrieve                 # Knowledge plane (optional)
  → domain.rca.prepare_llm_payload   # injects runbook_context
  → llm_chain (rca)
  → parse / validate
  → API projects RcaResponse
```

| Concern | Detail |
|---------|--------|
| Corpus | `spark-runbooks` (`config/corpora.yaml`) |
| Sample docs | `knowledge/spark-runbooks/*.md` |
| Backend | `EDIM_RETRIEVAL` — FAISS local / Azure deployed |
| Empty index | RCA still works; prompt notes no hits |

Full retrieval design: [Retrieval & RAG](../platform/retrieval-and-rag.md).

---

## Overrides for offline runs

| Agent | Field | Effect |
|-------|-------|--------|
| Tuning | `metrics` | Skip SQL collect |
| RCA | `evidence_pack` | Skip SQL collectors |

LLM nodes still run (use Foundry or test stub).

HTTP contracts: [endpoints](../api/endpoints.md).

---

← [SQL design deep dive](../DESIGN_SOURCES_AND_SQL_NODES.md) · [Guide home](../README.md) · [Agent package layout](../build-agents/agent-package-layout.md) →
