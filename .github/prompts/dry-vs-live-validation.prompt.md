---
name: dry-vs-live-validation
description: Plan or run dry (stub) vs live (Foundry/Databricks) validation for an agent
agent: agent
argument-hint: Agent name and whether dry, live, or both
---

# Dry vs live validation

## Dry (default / CI-friendly)

- Stub or local LLM if needed
- Client `evidence_pack` / metrics overrides to skip live SQL
- Memory recommendation store + memory/faiss retrieval as available
- Assert category/contract/quality gates and that optional web stays off unless testing it

## Live (explicit only)

- Requires credentials (`az login` / Foundry / Databricks) and a real target id
- Do not commit secrets; use `.env` locally (never paste keys into docs)
- Record pass/fail scenarios; defer live if the user cannot provide a target

Always prefer expanding dry coverage before requiring live for merge.
Update tests/docs with what was validated and what was deferred.
