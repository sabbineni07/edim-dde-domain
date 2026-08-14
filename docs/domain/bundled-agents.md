# Bundled agents (E3)

**Learning path:** E3 · [Guide home](../README.md)  
**← Previous:** [SQL design deep dive](../DESIGN_SOURCES_AND_SQL_NODES.md) · **Next:** [Agents deep dive](agents-guide.md) →

Shipped inside `edim-dde-domain` under `agents/`. Both follow [agent package layout](../build-agents/agent-package-layout.md) (`helpers/`, `content/`).

> **Full walkthroughs** (input → every graph node → outputs, Mermaid diagrams, UC attributes, knowledge add-ons): start at **[Agents deep dive](agents-guide.md)**.

---

## Overview

| `agent_id` | Purpose | Highlights |
|------------|---------|------------|
| `cluster_tuning` | Job cluster sizing recommendations | SQL metrics → sizing LLM → guardrails → **optional 1 re-prompt** → performance validation → risk → recommendation |
| `spark_rca` | Spark job root-cause analysis | SQL telemetry → evidence → classify → **runbook retrieve (RAG)** → RCA LLM |

| Walkthrough | UC catalog | Add-ons |
|-------------|------------|---------|
| [Cluster tuning](cluster-tuning-agent.md) · [Spark RCA](spark-rca-agent.md) | [UC telemetry tables](uc-telemetry-tables.md) | [External add-ons](external-addons.md) |

---

## Quick flow sketches

### `cluster_tuning`

```text
domain.sql.query (metrics)
  → prepare_sizing_payload → llm_chain(sizing) → parse_sizing (+ clamp)
  → if retryable clamps and attempts < 2: set guardrail_feedback → loop
  → validate_performance → assess_risks → generate_recommendation
  → optional explanation LLM
  → TuningResponse
```

### `spark_rca`

```text
domain.sql.query × 5 (anchors, plans, logs, timeline, stages)
  → assemble_evidence → classify → build_retrieval_query
  → rag.retrieve (spark-runbooks)
  → prepare_llm_payload → llm_chain(rca) → parse → validate
  → RcaResponse
```

---

## Overrides for offline runs

| Agent | Field | Effect |
|-------|-------|--------|
| Tuning | `metrics` | Skip SQL collect |
| RCA | `evidence_pack` | Skip SQL collectors |

LLM nodes still run (use Foundry or test stub).

HTTP contracts: [endpoints](../api/endpoints.md).

---

← [SQL design deep dive](../DESIGN_SOURCES_AND_SQL_NODES.md) · [Guide home](../README.md) · [Agents deep dive](agents-guide.md) →
