# Glossary (H3)

**Learning path:** H3 · [Preface](../README.md)  
**← Previous:** [Node type ids](node-type-ids.md) · **Next:** [Testing](../contribute/testing.md) →

## Chapter summary

Definitions of organizational names (**EDIM**, **DDE**) and platform terms used across this guide. Prefer this page over inventing synonyms.

---

| Term | Meaning |
|------|---------|
| **EDIM** | **E**nterprise **D**ata & **I**nformation **M**anagement — program under Enterprise Data & Analytics (portfolio or services) |
| **DDE** | **D**igital **D**ata **E**ngineering — engineering unit under the Digital business unit |
| **EDIM DDE** | The agent platform in this guide (`edim-dde-ai`, `edim-dde-domain`, `edim-dde-api`) — EDIM capabilities implemented by DDE |
| **Agent** | Named YAML graph + registered node types |
| **Node** | One graph step; type id → factory |
| **State** | Flat dict merged across nodes |
| **Bootstrap** | Load sources, import `nodes.py`, register YAML (± plugins) |
| **Content** | Prompts/skills for `llm_chain` |
| **Helper** | Agent-local pure module under `helpers/` |
| **Source** | Named Databricks SQL connection spec |
| **Override** | Request field that skips SQL: `metrics` (cluster tuning) or `evidence_pack` (RCA). Rest of the graph (RAG, Foundry, validate) still runs |
| **`evidence_pack`** | Structured RCA failure evidence (anchors, excerpts, refs). Built from UC SQL in prod, or supplied in the request / quality JSON for dry/smoke |
| **`metrics`** | One cluster-tuning telemetry row (SKU, util, workers). Built from UC SQL in prod, or supplied in the request / quality JSON for dry/smoke |
| **Quality harness** | Offline/live runner over `testdata/quality/`; fixtures score golden JSON; `--live` + `invoke_input` calls Foundry (inputs usually still from JSON unless SQL override omitted) |
| **Outcome correlation (2c)** | Join persisted `response.quality` bands with RecommendationStore `accepted`/`applied` via `evaluation.correlation` CLI; optional `extra.outcome` labels/reruns |
| **Plugin** | External agent dir or entry point registered at runtime |
| **HITL** | Human-in-the-loop — pause at `hitl.gate`, persist session, resume via `/api/v1/sessions/{id}/resume`. Guide: [HITL resume](../framework/hitl-resume.md) |
| **LangSmith** | LangChain tracing / eval product used for EDIM observability |
| **Observability provider** | Pluggable backend in `edim-dde-ai` (`langsmith` \| `mlflow` \| `none`) |
| **Control plane** | Catalog, sessions, audit — managed via `StateStore`, not SQL/LLM work. **Not** the future routing/governance plane — see [Agent control plane](../architecture/agent-control-plane.md) |
| **Agent control plane** | **Design only:** live location/policy/health repository + optional gateway. Does not execute graphs. Option B/C parked pending review |
| **Location registry** | Future: `agent_id` + env → where to invoke (not `AgentRecord` routing). Design: [Agent control plane](../architecture/agent-control-plane.md) |
| **`span_id` / `parent_span_id`** | Proposed per-invoke ids under a shared `request_id` for nested/remote agents. **Not implemented** — see control-plane §12 |
| **Data plane** | LangGraph execution, Databricks SQL, Foundry LLM |
| **StateStore** | Pluggable control-plane backend: `memory` \| `postgres` \| `cosmos` \| `redis` |
| **Checkpointer** | LangGraph session backend for multi-turn analysis: `memory` \| `postgres` via `EDIM_CHECKPOINTER` |
| **Conversation memory** | Bounded user/assistant context in graph checkpoints, selected by an agent's YAML `memory` + `session` policy; separate from HITL sessions and product recommendation history |
| **RecommendationStore** | Pluggable product-history backend for tuning (and future) recommendations: `none` \| `memory` \| `postgres` \| `cosmos` \| `redis` |
| **Experience index** | Derived resource-feature/action cards from RecommendationStore writes, upserted into a RetrievalProvider corpus for **feature** similarity (not job_id); see Retrieval & RAG §6c |
| **Agent catalog** | Metadata rows (`AgentRecord`) synced from registered YAML agents at bootstrap |
| **Similarity search** | Ranked document/chunk retrieval without an LLM |
| **RAG** | Retrieve → inject context → LLM answer (pattern built on RetrievalProvider) |
| **RetrievalProvider** | Pluggable search backend: `none` \| `memory` \| `faiss` \| `azure_ai_search` \| `databricks_vector` |
| **Corpus** | Logical knowledge collection (e.g. `spark-runbooks`) mapped via `corpora.yaml` |
| **R1** | Release 1 framework baseline (packages at `1.0.0`) |
| **SDBX / DEV / PROD** | Current environments (UAT / INTG documented for later) |
| **`request_id`** | Per-HTTP-call correlation id (`X-Request-Id` or generated); echoed on responses; appears on stdlib logs as `[request_id=…]` and LangSmith tags |
| **`sizing_attempts` / `guardrail_retries`** | Cluster tuning: count of sizing LLM calls and how many were re-prompts after clamp violations (max 2 attempts) |
| **`performance_validation`** | Cluster tuning: rule-based check that recommended capacity likely meets peak load (`meets_peak_requirements`, `estimated_impact`, …) |
| **`cluster_tuning/recommend`** | HTTP path for the cluster sizing agent (`POST /api/v1/cluster_tuning/recommend`); replaces legacy `/api/v1/recommendations` |

<!-- edim-learning-nav -->
---

← [Node type ids](node-type-ids.md) · [Preface](../README.md) · [Testing](../contribute/testing.md) →
