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
| **Agent catalog** | Metadata rows (`AgentRecord`) synced from registered YAML agents at bootstrap |
| **Similarity search** | Ranked document/chunk retrieval without an LLM |
| **RAG** | Retrieve → inject context → LLM answer (pattern built on RetrievalProvider) |
| **RetrievalProvider** | Pluggable search backend: `none` \| `memory` \| `faiss` \| `azure_ai_search` \| `databricks_vector` |
| **Corpus** | Logical knowledge collection (e.g. `spark-runbooks`) mapped via `corpora.yaml` |
| **R1** | Release 1 framework baseline (packages at `1.0.0`) |
| **SDBX / DEV / PROD** | Phase 0 environments (UAT / INTG documented for later) |

<!-- edim-learning-nav -->
---

← [Node type ids](node-type-ids.md) · [Guide home](../README.md) · [Testing](../contribute/testing.md) →
