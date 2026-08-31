# Guide map (A0)

**Learning path:** A0 · [Preface](../README.md)  
**← Previous:** [Preface](../README.md) · **Next:** [Quickstart (A1)](quickstart.md) →

## Chapter summary

This page is the **table of contents** for the EDIM DDE Engineer Guide. Sidebar sections **A–H**, footer **Previous / Next**, and `mkdocs.yml` `nav` all follow this order.

---

## Reading paths by role

| Role | Recommended sequence |
|------|----------------------|
| **New to EDIM** | Preface → A1 Quickstart → A2 Concepts → [Part B](../architecture/index.md) |
| **Platform / deploy** | A1 → [Part C](../platform/index.md) → [Part G](../api/index.md) → H5 smoke |
| **Agent author** | A2 → [Part D](../framework/index.md) → [Part F](../build-agents/index.md) |
| **Architect** | A2 → B1 End-to-end design → B4 Reference architecture |
| **Operator / SRE** | G2 Endpoints → H5 Live smoke → C2b Access & permissions |

---

## Part A — Start here

| Step | Chapter | Description |
|------|---------|-------------|
| **A0** | Guide map | This page |
| **A1** | [Quickstart](quickstart.md) | Install and first HTTP call |
| **A2** | [Core concepts](concepts.md) | Vocabulary |

---

## Part B — Architecture

**Overview:** [Part B — Architecture](../architecture/index.md)

| Step | Chapter | Description |
|------|---------|-------------|
| **B1** | [End-to-end design](../architecture/end-to-end-design.md) | Master design reference |
| **B2** | [Overview](../architecture/overview.md) | System sketch |
| **B3** | [Packages](../architecture/packages.md) | Package boundaries |
| **B4** | [Reference architecture](../architecture/reference-architecture.md) | Sign-off map |
| **B5** | [Architecture deck](../architecture/architecture-deck.md) | Slides |
| **B6** | [Request flow](../architecture/request-flow.md) | HTTP trace |
| **B7** | [Auth and SQL](../architecture/auth-and-sql.md) | Token resolution |
| **B8** | [Config → observability](../architecture/config-to-observability.md) | YAML to traces |
| **B9** | [Agent deployment](../architecture/agent-deployment-and-composition.md) | Hosting shapes |
| **B9b** | [Control plane (design)](../architecture/agent-control-plane.md) | Parked — not R1 |

---

## Part C — Platform

**Overview:** [Part C — Platform](../platform/index.md)

| Step | Chapter | Description |
|------|---------|-------------|
| **C1** | [Environments](../platform/environments.md) | `EDIM_ENV` matrix |
| **C2–C2c** | Security, access, KV | Identity and secrets |
| **C3** | [PII guardrails](../platform/pii-guardrails.md) | Redaction |
| **C4–C5** | Observability, LangSmith | Tracing |
| **C6–C6b** | State, recommendation stores | Persistence |
| **C7** | [Retrieval & RAG](../platform/retrieval-and-rag.md) | Knowledge plane |

---

## Part D — Framework

**Overview:** [Part D — Framework](../framework/index.md)

| Step | Chapter | Description |
|------|---------|-------------|
| **D1–D2** | Schema, YAML agents | Declarative graphs |
| **D3–D4** | Nodes, conditional edges | Graph mechanics |
| **D5–D6** | Content/LLM, orchestration | Chains, nesting |
| **D6b** | [HITL resume](../framework/hitl-resume.md) | Human gates |
| **D7** | [Evaluation](../framework/evaluation-and-quality.md) | Quality harness |

---

## Part E — Domain

**Overview:** [Part E — Domain](../domain/index.md)

| Step | Chapter | Description |
|------|---------|-------------|
| **E1–E2** | Sources, SQL design | Data collection |
| **E3–E3e** | Bundled agents, walkthroughs | Product graphs |

---

## Part F — Build agents

**Overview:** [Part F — Build agents](../build-agents/index.md)

| Step | Chapter | Description |
|------|---------|-------------|
| **F1–F3** | Layout, step-by-step, plugins | Authoring |

---

## Part G — API host

**Overview:** [Part G — API host](../api/index.md)

| Step | Chapter | Description |
|------|---------|-------------|
| **G1–G2** | Config, endpoints | HTTP host |
| **G3a** | [Deployment targets](../api/deployment-targets.md) | Package and select a host |
| **G3** | [Deploy & hosting](../api/deploy-and-hosting.md) | Compatibility commands |

---

## Part H — Reference

**Overview:** [Part H — Reference](../reference/index.md)

| Step | Chapter | Description |
|------|---------|-------------|
| **H1–H3** | Env vars, node ids, glossary | Lookup |
| **H4–H6** | Testing, smoke, packaging | Contribute |
| — | [Documentation style](../contribute/documentation-style.md) | Writing conventions |

**Git-only:** `VALIDATION.md`, `BACKLOG.md` at workspace root.

---

## Summary

Use **sequential navigation** (Previous / Next) for first read. Use **Part overview** pages when jumping into a section. **Preface** defines scope and conventions.

← [Preface](../README.md) · [Quickstart (A1)](quickstart.md) →
