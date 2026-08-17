# HTML architecture deck (B5)

**Learning path:** B5 · [Guide home](../README.md)  
**← Previous:** [Reference architecture](reference-architecture.md) · **Next:** [Request flow](request-flow.md) →

Open the slide deck for architecture reviews and PowerPoint capture:

**→ [Open HTML deck (Present mode)](diagrams/r1-architecture-deck.html)**

### Speaker line (slide 03 — packages)

> We split the stack on a hard boundary: **ai** is the reusable agent runtime;
> **domain** is Databricks plus this product’s agents; **api** is a thin HTTP host.
> YAML composes graphs; Python is allowlisted. The framework never talks to Unity Catalog.

That is the intended contract. Today, a few safety/quality helpers still live in domain
(PII patterns, quality harness) and may move into ai later — do not over-claim file locations.

| Asset | Use |
|-------|-----|
| [r1-architecture-deck.html](diagrams/r1-architecture-deck.html) | Chrome → **Present** → capture 1280×720 slides into PPT |
| [r1-system-context.svg](diagrams/r1-system-context.svg) | Insert as vector in PPT |
| [r1-request-sequence.svg](diagrams/r1-request-sequence.svg) | Insert as vector in PPT |
| [r1-environments.svg](diagrams/r1-environments.svg) | Insert as vector in PPT |

Sign-off narrative and non-goals stay in [reference architecture](reference-architecture.md). Continue the learning path at [request flow](request-flow.md).

<!-- edim-learning-nav -->
---

← [Reference architecture](reference-architecture.md) · [Guide home](../README.md) · [Request flow](request-flow.md) →
