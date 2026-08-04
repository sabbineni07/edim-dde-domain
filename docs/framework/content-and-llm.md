# Content and LLM (D5)

**Learning path:** D5 · [Guide home](../README.md)  
**← Previous:** [Conditional edges](conditional-edges.md) · **Next:** [Orchestration](orchestration-topology.md) →

How prompts, skills, and the LLM Strategy are wired into `llm_chain` nodes.

---

## 1. Design patterns

| Pattern | Where |
|---------|-------|
| **Strategy** | `LLMProvider` — Foundry vs stub vs custom |
| **Facade** | `ContentHub` resolves prompts/skills with a clear override order |
| **Template Method** | `build_chat_messages` loads roles, substitutes `{var}`, optional skills |

Resolution order for prompts/skills:

```text
1. Process-wide user override provider (if set)
2. Per-agent content_dir (DirectoryContentProvider)
3. Inline YAML prompts: / skills: (InlineContentStore)
```

---

## 2. Content hub

On register, if the YAML has `prompts` / `skills` / `content_dir`, content is loaded into the process-wide ContentHub.

Directory layout (typical):

```text
content/
  prompts/
    sizing.system.md
    sizing.human.md
    rca.system.md
    rca.human.md
  skills/
    *.md
```

`llm_chain` nodes reference a `chain` name and optionally `attach_skills: true`.

Human prompts use `{state_key}` placeholders — e.g. `{runbook_context}` for the RCA RAG pilot.

---

## 3. LLM provider

```python
from edim_dde_ai import set_llm_provider

set_llm_provider(my_provider)  # Protocol: invoke(messages, *, config=None) -> str
```

| Implementation | Use |
|----------------|-----|
| `FoundryLLMProvider` (domain) | Azure OpenAI via Foundry — production |
| Lazy wrapper (API lifespan) | Construct Foundry on first invoke so `/health` works early |
| `DomainStubLLM` (tests) | Offline CI without cloud |

Hosts **must** set a provider before invoking graphs that use `llm_chain` without a custom chain invoker.

Chain invokers (optional Strategy): if `register_chain_invoker(name)` exists, it wins over ContentHub+LLMProvider for that `chain` name.

---

## 4. Flow

```text
llm_chain config {chain: rca, attach_skills: true}
  → build_chat_messages(agent_id, chain, state)
  → LLMProvider.invoke(messages)
  → {output_key: text}
```

Foundry auth: local `az login` or SP from Key Vault — see [auth and SQL](../architecture/auth-and-sql.md) and [configuration](../api/configuration.md).

---

← [Conditional edges](conditional-edges.md) · [Guide home](../README.md) · [Orchestration](orchestration-topology.md) →
