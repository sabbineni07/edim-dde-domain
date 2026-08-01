# Glossary

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
| **R1** | Release 1 framework baseline (packages at `1.0.0`) |
| **SDBX / DEV / PROD** | Phase 0 environments (UAT / INTG documented for later) |
