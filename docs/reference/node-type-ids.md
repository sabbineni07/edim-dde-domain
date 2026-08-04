# Node type ids

**Learning path:** H2 · [Guide home](../README.md)
**← Previous:** [Environment variables](env-vars.md) · **Next:** [Glossary](glossary.md) →


## Framework builtins (`edim-dde-ai`)

| Type id | Role |
|---------|------|
| `passthrough` | No-op |
| `set_value` | Set a field (literal or `{template}`) |
| `echo_result` | Build `result` from listed fields |
| `llm_chain` | Prompt + skills + LLMProvider / invoker |
| `invoke_agent` | Call another registered agent (subgraph spike; depth-limited) |
| `rag.retrieve` | Similarity / hybrid search via RetrievalProvider |

## Domain shared

| Type id | Role |
|---------|------|
| `domain.sql.query` | Named-source SQL collect |

## Bundled product (examples)

| Prefix | Agent |
|--------|-------|
| `domain.tuning.*` | cluster_tuning |
| `domain.rca.*` | spark_rca (includes `build_retrieval_query` for RAG pilot) |

Plugins should use their own prefix (e.g. `acme.*`).

<!-- edim-learning-nav -->
---

← [Environment variables](env-vars.md) · [Guide home](../README.md) · [Glossary](glossary.md) →
