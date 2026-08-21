# Bundled agents (E3)

**Learning path:** E3 · [Preface](../README.md)  
**← Previous:** [SQL design deep dive](../DESIGN_SOURCES_AND_SQL_NODES.md) · **Next:** [Agents deep dive](agents-guide.md) →

## Chapter summary

Catalog of agents shipped in `edim-dde-domain` under `agents/` (`cluster_tuning`, `spark_rca`), following the standard package layout. Full node-by-node walkthroughs live in the agents deep-dive section.

**Outcome:** you know which bundled agents exist and where to open the detailed graphs.

---

Shipped inside `edim-dde-domain` under `agents/`. Both follow [agent package layout](../build-agents/agent-package-layout.md) (`helpers/`, `content/`).

> **Full walkthroughs** (input → every graph node → outputs, Mermaid diagrams, UC attributes, knowledge add-ons): start at **[Agents deep dive](agents-guide.md)**.

---

## Overview

| `agent_id` | Purpose | Highlights |
|------------|---------|------------|
| `cluster_tuning` | Job cluster sizing recommendations | SQL metrics → sizing LLM → guardrails → **optional 1 re-prompt** → performance validation → risk → recommendation |
| `spark_rca` | Spark job root-cause analysis | SQL telemetry → evidence → classify → **runbook retrieve (RAG)** → RCA LLM |
| `hitl_demo` | HITL pause / resume sample | `set_value` → `hitl.gate` → finish. No SQL/LLM. [HITL guide](../framework/hitl-resume.md) |

| Walkthrough | UC catalog | Add-ons |
|-------------|------------|---------|
| [Cluster tuning](cluster-tuning-agent.md) · [Spark RCA](spark-rca-agent.md) | [UC telemetry tables](uc-telemetry-tables.md) | [External add-ons](external-addons.md) |

---

## Quick flow diagrams (DFD-style)

Legend: **blue** = external actor / system · **orange rectangle** = data store · **gold circle** = process step · arrows are labeled with what moves.

### `cluster_tuning`

```mermaid
flowchart TB
  classDef external fill:#5B8DEF,stroke:#2F5BB7,color:#fff
  classDef store fill:#F4A261,stroke:#C47A3A,color:#1a1a1a
  classDef process fill:#E9C46A,stroke:#B08900,color:#1a1a1a
  classDef out fill:#2A9D8F,stroke:#1F7A6E,color:#fff

  Client[Client / API]:::external
  UC[(UC job cluster metrics)]:::store
  Foundry[Azure AI Foundry]:::external
  Resp[TuningResponse]:::out

  Collect((collect metrics)):::process
  Prep((prepare sizing)):::process
  Size((sizing LLM)):::process
  Parse((parse + guardrails)):::process
  Perf((validate performance)):::process
  Risk((assess risks)):::process
  Gen((generate recommendation)):::process
  Expl((explanation LLM)):::process

  Client -->|job_id, cluster_id<br/>or metrics override| Collect
  UC -->|metrics row| Collect
  Collect --> Prep
  Prep -->|prompt fields| Size
  Foundry -->|completion| Size
  Size -->|sizing_raw| Parse
  Parse -->|retryable clamp<br/>attempts &lt; 2| Prep
  Parse -->|clamped sizing| Perf
  Perf --> Risk
  Risk --> Gen
  Gen -->|include_explanation| Expl
  Foundry -.->|optional| Expl
  Gen -->|DTO fields| Resp
  Expl --> Resp
  Resp -->|JSON + X-Request-Id| Client
```

### `spark_rca`

```mermaid
flowchart TB
  classDef external fill:#5B8DEF,stroke:#2F5BB7,color:#fff
  classDef store fill:#F4A261,stroke:#C47A3A,color:#1a1a1a
  classDef process fill:#E9C46A,stroke:#B08900,color:#1a1a1a
  classDef out fill:#2A9D8F,stroke:#1F7A6E,color:#fff

  Client[Client / API]:::external
  Metrics[(UC spark metrics)]:::store
  Logs[(UC spark logs)]:::store
  Index[(Runbook index<br/>FAISS / Azure / DBX)]:::store
  Foundry[Azure AI Foundry]:::external
  Resp[RcaResponse]:::out

  Collect((collect ×5 SQL)):::process
  Assemble((assemble evidence)):::process
  Classify((rule classify)):::process
  Query((build retrieval query)):::process
  Retrieve((rag.retrieve)):::process
  Prep((prepare LLM payload)):::process
  Synth((RCA LLM)):::process
  Validate((parse + validate)):::process

  Client -->|job_run_id<br/>or evidence_pack| Collect
  Metrics -->|anchors, plans,<br/>timeline, stages| Collect
  Logs -->|errors / exceptions| Collect
  Collect --> Assemble --> Classify --> Query
  Query -->|retrieval_query| Retrieve
  Index -->|runbook hits| Retrieve
  Retrieve --> Prep --> Synth
  Foundry -->|completion| Synth
  Synth --> Validate --> Resp
  Resp -->|JSON + X-Request-Id| Client
```

Detail with every YAML node id: [Cluster tuning](cluster-tuning-agent.md) · [Spark RCA](spark-rca-agent.md).

---

## Overrides for offline runs

| Agent | Field | Effect |
|-------|-------|--------|
| Tuning | `metrics` | Skip SQL collect |
| RCA | `evidence_pack` | Skip SQL collectors |

LLM nodes still run (use Foundry or test stub).

HTTP contracts: [endpoints](../api/endpoints.md).

---

## Summary

- Two product agents ship in-domain; both follow package layout conventions.
- Dry overrides skip SQL; HTTP contracts are on the API endpoints page.

**Next →** [Agents deep dive (E3a)](agents-guide.md)

← [SQL design deep dive](../DESIGN_SOURCES_AND_SQL_NODES.md) · [Preface](../README.md) · [Agents deep dive](agents-guide.md) →
