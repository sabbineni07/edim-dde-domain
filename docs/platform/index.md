# Part C — Platform

**Learning path:** C0 · [Home](../README.md)  
**← Previous:** [Agent deployment & composition](../architecture/agent-deployment-and-composition.md) · **Next:** [Environments](environments.md) →

## Chapter overview

Part C documents **runtime planes** configured at API startup: environments, security identities, secrets, observability, persistence, and retrieval. The chapter order mirrors `edim-dde-api` lifespan initialization so documentation aligns with production behavior.

**After completing Part C you will:**

- Map Local, Databricks Apps, and ACA hosts to identities **U** (user), **A** (host), **B** (Foundry).
- Configure StateStore, RecommendationStore, and RetrievalProvider backends via env vars.
- Bootstrap Key Vault secrets without polluting SQL credential chains.

---

## Prerequisites

| Requirement | Chapter |
|-------------|---------|
| Planes and package model | [End-to-end design (B1)](../architecture/end-to-end-design.md) |
| Auth overview | [Auth and SQL (B7)](../architecture/auth-and-sql.md) |

---

## Chapters in this part

| Step | Chapter | Plane / concern |
|------|---------|-----------------|
| **C1** | [Environments](environments.md) | SDBX / DEV / PROD; `EDIM_ENV` |
| **C2** | [Security baseline](security-baseline.md) | Trust boundaries, role matrix |
| **C2b** | [Access & permissions](access-and-permissions.md) | U/A/B per host |
| **C2b-flow** | [Authentication flows](authentication-flows.md) | End-to-end auth diagrams |
| **C2c** | [Key Vault bootstrap](key-vault-bootstrap.md) | `EDIM_KV_SECRET_MAP` |
| **C3** | [PII guardrails](pii-guardrails.md) | Redaction before logs/traces |
| **C4** | [Observability](observability.md) | LangSmith / MLflow / none |
| **C5** | [LangSmith setup](langsmith-setup.md) | Tracing validation |
| **C6** | [State store](state-store.md) | Catalog, sessions, audit |
| **C6b** | [Recommendation store](recommendation-store.md) | Tuning/RCA history |
| **C7** | [Retrieval & RAG](retrieval-and-rag.md) | Vector / keyword search |

---

## Security topic routing

| Question | Read |
|----------|------|
| Who may call the warehouse on Apps? | **C2b**, **C2b-flow**, [Deploy G3](../api/deploy-and-hosting.md) |
| How does Foundry authenticate? | **C2c**, [Configuration G1](../api/configuration.md) |
| Where do sessions persist? | **C6**, [HITL D6b](../framework/hitl-resume.md) |

!!! warning "Apps SQL requires user scope"
    On Databricks Apps, live SQL needs **User authorization scope `sql`** and the gateway-injected `X-Forwarded-Access-Token`. App SP warehouse grants alone are insufficient for bundled agents.

---

## Summary

Configure platform planes before enabling live SQL, Foundry, or RAG in non-dev environments. Start with **C1** and **C2b**.

**Next →** [Environments (C1)](environments.md)
