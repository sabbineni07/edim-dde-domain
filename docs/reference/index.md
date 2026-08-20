# Part H — Reference & contribute

**Learning path:** H0 · [Home](../README.md)  
**← Previous:** [Deploy & hosting](../api/deploy-and-hosting.md) · **Next:** [Environment variables](env-vars.md) →

## Chapter overview

Part H collects **lookup tables**, validation runbooks, and contributor workflows. Use it after Parts A–G when you need exact env names, node type ids, or smoke procedures.

---

## Chapters in this part

| Step | Chapter | Use when |
|------|---------|----------|
| **H1** | [Environment variables](env-vars.md) | Looking up `EDIM_*` / Databricks / Azure vars |
| **H2** | [Node type ids](node-type-ids.md) | Choosing or registering node `type` strings |
| **H3** | [Glossary](glossary.md) | Term definitions |
| **H4** | [Testing](testing.md) | Running `pytest` across packages |
| **H5** | [Live smoke test](live-smoke-test.md) | Dry + live HTTP validation |
| **H5b** | [Windows smoke checklist](windows-smoke-checklist.md) | PowerShell-oriented smoke |
| **H6** | [Packaging](packaging.md) | Wheels and private index |
| — | [Documentation style](../contribute/documentation-style.md) | Editing this guide |

**Git-only (not in MkDocs):** workspace `VALIDATION.md`, `BACKLOG.md`.

---

## Recommended validation path

1. **H4** — unit tests green on all three packages.
2. **H5** or **H5b** — dry then live smoke against your target host.
3. **H1** — verify env catalog matches your `.env` / `app.yaml`.

---

## Summary

Part H is intentionally **reference-first** — bookmark **H1** and **H3** during implementation.

**Next →** [Environment variables (H1)](env-vars.md)
