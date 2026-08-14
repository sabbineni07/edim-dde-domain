# Glossary

**Learning path:** H3 · [Guide home](../README.md)
**← Previous:** [Node type ids](node-type-ids.md) · **Next:** [Testing](../contribute/testing.md) →


| Term | Meaning |
|------|---------|
| **Agent** | Named YAML graph + registered node types |
| **Node** | One graph step; type id → factory |
| **State** | Flat dict merged across nodes |
| **Bootstrap** | Load sources, import `nodes.py`, register YAML (± plugins) |
| **Content** | Prompts/skills for `llm_chain` |
| **Helper** | Agent-local pure module under `helpers/` |
| **Source** | Named Databricks SQL connection spec |
| **Override** | Request field that skips SQL (`metrics`, `evidence_pack`) |
| **Plugin** | External agent dir or entry point registered at runtime |
| **HITL** | Human-in-the-loop — human review/approval in the agent workflow |
| **LangSmith** | LangChain tracing / eval product used for EDIM observability |
| **Observability provider** | Pluggable backend in `edim-dde-ai` (`langsmith` \| `mlflow` \| `none`) |
| **Control plane** | Catalog, sessions, audit — managed via `StateStore`, not SQL/LLM work |
| **Data plane** | LangGraph execution, Databricks SQL, Foundry LLM |
| **StateStore** | Pluggable control-plane backend: `memory` \| `postgres` \| `cosmos` \| `redis` |
| **RecommendationStore** | Pluggable product-history backend for tuning (and future) recommendations: `none` \| `memory` \| `postgres` \| `cosmos` \| `redis` |
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

← [Node type ids](node-type-ids.md) · [Guide home](../README.md) · [Testing](../contribute/testing.md) →
