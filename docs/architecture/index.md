# Part B — Architecture

**Learning path:** B0 · [Preface](../README.md)  
**← Previous:** [Core concepts](../getting-started/concepts.md) · **Next:** [End-to-end design](end-to-end-design.md) →

## Chapter overview

Part B establishes the **system design** of EDIM DDE: planes of responsibility, package boundaries, authentication paths, and deployment composition. Read this part before changing runtime wiring or adding cross-cutting infrastructure.

**After completing Part B you will:**

- Explain how a single HTTP request traverses API → domain → LangGraph → SQL/LLM/RAG.
- Distinguish control, knowledge, data, and observability planes.
- Choose an appropriate deployment shape (one App vs split hosts) within R1 constraints.

---

## Prerequisites

| Requirement | Chapter |
|-------------|---------|
| Local stack or test familiarity | [Quickstart (A1)](../getting-started/quickstart.md) |
| Agent, node, state vocabulary | [Core concepts (A2)](../getting-started/concepts.md) |

---

## Chapters in this part

| Step | Chapter | Focus |
|------|---------|-------|
| **B1** | [End-to-end design](end-to-end-design.md) | Master reference — planes, patterns, lifecycle |
| **B1b** | [Inner vs outer architecture](inner-outer-architecture.md) | Inner (R1) vs outer (planned), R1 vs target |
| **B2** | [Overview](overview.md) | One-page system sketch |
| **B3** | [Packages](packages.md) | `ai` / `domain` / `api` ownership |
| **B4** | [Reference architecture](reference-architecture.md) | Sign-off map, trust boundaries, non-goals |
| **B5** | [Architecture deck](architecture-deck.md) | Presentation assets |
| **B6** | [Request flow](request-flow.md) | `cluster_tuning` call trace |
| **B7** | [Auth and SQL](auth-and-sql.md) | Warehouse token resolution |
| **B8** | [Config → observability](config-to-observability.md) | YAML to traces and stores |
| **B9** | [Agent deployment & composition](agent-deployment-and-composition.md) | Multi-agent hosting, SDLC |
| **B9b** | [Agent control plane](agent-control-plane.md) | **Design only** — parked for post-R1 |

!!! note "Reading order"
    **B1** is the canonical deep dive. **B1b** defines inner (what we run) vs outer (what we plan). **B2–B3** are executive summaries. **B6–B8** are implementation companions. **B9b** is optional design review material — not required for R1 delivery.

---

## Architectural invariants (R1)

1. **One process = one `EDIM_ENV`.** No cross-environment SQL or agent I/O in a single deployment.
2. **Git is SoT for graphs and prompts.** StateStore holds catalog/sessions/audit — not routing graphs.
3. **YAML references allowlisted node types only.** No arbitrary Python imports in agent YAML.
4. **Product agents do not embed HTTP or tracing SDKs.** Planes are configured at API lifespan.

---

## Summary

Part B answers *what the system is* and *how requests move*. Proceed to **B1** for the full design narrative, then **Part C** for operational plane configuration.

**Next →** [End-to-end design (B1)](end-to-end-design.md)
