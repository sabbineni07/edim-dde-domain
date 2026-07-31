# Content and LLM

## Content hub

On register, if the YAML has `prompts` / `skills` / `content_dir`, content is loaded into the process-wide ContentHub.

Directory layout (typical):

```text
content/
  prompts/
    sizing.system.md
    sizing.human.md
  skills/
    *.md
```

`llm_chain` nodes reference a `chain` name and optionally `attach_skills: true`.

## LLM provider

```python
from edim_dde_ai import set_llm_provider

set_llm_provider(my_provider)  # Protocol: invoke(messages, *, config=None) -> str
```

Domain ships `FoundryLLMProvider`. The API installs a lazy wrapper at startup. Tests use `edim_dde_domain.testing.DomainStubLLM`.

Hosts **must** set a provider before invoking graphs that use `llm_chain` without a custom chain invoker.
