# Documentation style guide

**Audience:** contributors editing the EDIM DDE engineer guide (`edim-dde-domain/docs/`).

This guide defines the **book-style** conventions used across all chapters. Match this voice and structure when adding or revising pages.

---

## Voice and tone

| Do | Avoid |
|----|--------|
| Write in present tense, active voice | Marketing fluff, exclamation marks, “simply” / “just” |
| Define terms once, then use consistently | Undefined acronyms; synonyms for the same concept |
| State constraints and failure modes explicitly | Hand-waving (“should work”, “might need”) without conditions |
| Use **must**, **should**, **may** with precise meaning (required / recommended / optional) | Casual asides that bury requirements |

**Reference quality bar:** O'Reilly / Manning engineering books — precise, scannable, implementation-oriented.

---

## Page anatomy

Every guide page (except Home) should include, in order:

1. **Title** — `# Chapter title (section id)` e.g. `# Quickstart (A1)`
2. **Learning path line** — section id, home link, prev/next
3. **Chapter summary** — 2–4 sentences: purpose, audience, outcome
4. **Prerequisites** (when non-obvious) — bullet list with links
5. **Body** — hierarchical `##` / `###`; prefer tables and numbered steps over prose walls
6. **Pro tips / warnings** — MkDocs admonitions (`!!! tip`, `!!! warning`, `!!! note`)
7. **Troubleshooting** (implementation chapters) — symptom → cause → fix table
8. **Summary** — bullet recap + explicit next chapter link
9. **Footer nav** — `← Previous · Next →`

### Learning path header (required)

```markdown
**Learning path:** A1 · [Home](../README.md)  
**← Previous:** [Guide map](guide-map.md) · **Next:** [Core concepts](concepts.md) →
```

Adjust relative paths per folder depth. **Section ids** must match `mkdocs.yml` order (see [Guide map](../getting-started/guide-map.md)).

---

## Admonitions

```markdown
!!! tip "Pro tip"
    Prefer `EDIM_STATE_STORE=memory` for first local smoke; switch to Postgres when testing persistence.

!!! warning "Production constraint"
    Never commit Foundry client secrets. Use Key Vault or Databricks Apps secrets.

!!! note "Design note"
    Option C (remote agent routing) is **design only** — not implemented in R1.
```

---

## Code and configuration

- **Shell:** use `bash` fences; show full commands (no `...` omissions in copy-paste blocks).
- **YAML:** cite real keys from `*.agent.yaml` or `app.yaml`; annotate non-obvious fields.
- **Env vars:** monospace names; link to [Environment variables](../reference/env-vars.md) for catalog entries.
- **HTTP:** show method, path, minimal JSON body, and expected status codes.

---

## Section parts (A–H)

| Part | Role | Chapter opener |
|------|------|----------------|
| **A** | Onboarding | [Guide map](../getting-started/guide-map.md) |
| **B** | Architecture | [architecture/index.md](../architecture/index.md) |
| **C** | Platform planes | [platform/index.md](../platform/index.md) |
| **D** | Framework (`edim-dde-ai`) | [framework/index.md](../framework/index.md) |
| **E** | Domain agents & SQL | [domain/index.md](../domain/index.md) |
| **F** | Authoring new agents | [build-agents/index.md](../build-agents/index.md) |
| **G** | API host | [api/index.md](../api/index.md) |
| **H** | Reference & contribute | [reference/index.md](../reference/index.md) |

Each part opener lists chapters, prerequisites, and recommended reading order within the part.

---

## Navigation source of truth

1. **`mkdocs.yml` `nav`** — sidebar order  
2. **Page prev/next headers** — must agree with `nav`  
3. **[Guide map](../getting-started/guide-map.md)** — human-readable TOC  

When adding a page, update all three.

---

## Building the site locally

```bash
cd edim-dde-api
make guide-site && make compose-up
# open http://127.0.0.1:8080/guide/
```

---

**Learning path:** H6 · [Home](../README.md)  
**← Previous:** [Packaging](packaging.md) · **Next:** [Home](../README.md) →
