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
