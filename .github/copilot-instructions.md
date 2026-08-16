# EDIM DDE Domain — GitHub Copilot instructions

> **Team source of truth for VS Code + GitHub Copilot.**  
> Keep the shared “EDIM DDE practices” section aligned with sibling repos `edim-dde-ai` and `edim-dde-api`.  
> Deep design: `docs/` (MkDocs). Keep this file short and actionable.

This package owns **product agents** (YAML + nodes + logic + prompts/skills/runbooks), SQL/sources, Foundry LLM wiring, and domain evaluators. It depends on `edim-dde-ai` for graph runtime and platform seams.

---

## Shared EDIM DDE practices (keep aligned across repos)

### Separation of concerns

- Prefer **config-driven composition** (agent YAML + registered node ids) over hard-coded graphs.
- Put **swappable backends** behind framework Strategy protocols (retrieval, recommendation store, web search, LLM).
- **Fail soft** for secondary lanes (history, runbooks, web): empty/`None` is OK; do not fail the primary request.
- Live **evidence / metrics** are authoritative; history and web are hints only — never invent citations.

### Design patterns (prefer these)

| Prefer | Use for |
|--------|---------|
| Registry | `@register_node`, evaluators, experience transforms |
| Strategy | Providers from `edim-dde-ai` (do not call vendor SDKs from agent helpers) |
| Factory | Thin `nodes.py` factories that close over YAML config |
| Pure helpers | `logic.py` + `helpers/` — no HTTP, no LangGraph imports in helpers when avoidable |
| Null / empty | `"None"` history, empty web query when disabled |

### Code quality

- **DRY**: mirror patterns across agents (experience transform, historical context, quality evaluator) instead of one-off copies with divergent semantics.
- **Docstrings**: module Business purpose / Public API; public APIs get Args/Returns.
- **Inline comments**: non-obvious rules only (acceptance gates, PII-safe egress, citation allowlists).
- Prefer YAML knobs for new signals/thresholds when the engine is already dimension-agnostic.

### Testing & validation

- Unit-test classify / validate / experience / historical_context / evaluators with packs and memory stores.
- **Dry**: `evidence_pack` / metrics overrides + stub LLM. **Live**: real Databricks SQL / Foundry — optional; do not require for merge when dry coverage is solid.
- Assert negatives where taxonomy lock-in is a risk (no closed scenario enums as primary retrieval keys).

### Documentation

- Update agent docs under `docs/domain/` and platform notes when adding lanes (experience, web, lifecycle).
- Generated `site/` is build output — do not commit.

---

## This package (`edim-dde-domain`) — boundaries

### Agent layout

Each agent directory owns:

- `*.agent.yaml` — graph topology + knobs
- `nodes.py` — thin factories only
- `logic.py` — pure state → patch business logic
- `helpers/` — classify, validate, evidence, experience, history, policy
- `content/` — prompts, skills
- `knowledge/` — curated corpora files when applicable

### Product rules

- **SQL** via `domain.sql.query` / tools — not ad-hoc SDK calls inside graph nodes.
- **RCA**: live `evidence_pack` is authoritative; runbooks ≠ experience outcomes (separate prompt lanes).
- **Experience index**: structural/open features; do not key retrieval primarily on closed scenario enums or `job_id`.
- **Acceptance gate** (RCA): cross-job experience cards for `accepted`/`applied` only; `proposed` stays on exact entity history.
- **Web search**: YAML `enabled` default off; sanitize queries (exception-class tokens); PII redact defense-in-depth; allowlisted domains.
- **Quality**: deterministic evaluators (`*.quality`); evaluator confidence ≠ model confidence.

### Bootstrap

Register nodes, experience transforms, and evaluators from `bootstrap.py` — importing node modules must be enough to register factories.
