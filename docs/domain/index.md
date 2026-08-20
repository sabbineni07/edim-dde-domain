# Part E — Domain

**Learning path:** E0 · [Home](../README.md)  
**← Previous:** [Evaluation & quality](../framework/evaluation-and-quality.md) · **Next:** [Sources and SQL](sources-and-sql.md) →

## Chapter overview

Part E documents **`edim-dde-domain`**: named SQL sources, the generic `domain.sql.query` node, workspace resolution within an environment, and the bundled **cluster tuning** and **Spark RCA** product agents.

**After completing Part E you will:**

- Bind telemetry tables via `config/sources.yaml` and env-driven FQNs.
- Trace each bundled agent from HTTP payload to response DTO.
- Extend evidence collection without per-use-case SQL collector classes.

---

## Prerequisites

| Requirement | Chapter |
|-------------|---------|
| SQL auth model | [Auth and SQL (B7)](../architecture/auth-and-sql.md) |
| Node type pattern | [Nodes and routers (D3)](../framework/nodes-and-routers.md) |

---

## Chapters in this part

| Step | Chapter | Topic |
|------|---------|-------|
| **E1** | [Sources and SQL](sources-and-sql.md) | Named sources, connection shape |
| **E1b** | [Workspace resolver](workspace-resolver.md) | Within-env FQNs |
| **E2** | [Sources design (deep)](../DESIGN_SOURCES_AND_SQL_NODES.md) | Rationale for one SQL node |
| **E3** | [Bundled agents](bundled-agents.md) | Agent map |
| **E3a** | [Agents deep dive](agents-guide.md) | Shared dependencies hub |
| **E3b** | [Cluster tuning walkthrough](cluster-tuning-agent.md) | Full tuning graph |
| **E3c** | [Spark RCA walkthrough](spark-rca-agent.md) | Multi-SQL + RAG |
| **E3d** | [UC telemetry tables](uc-telemetry-tables.md) | Table catalog |
| **E3e** | [External add-ons](external-addons.md) | Foundry, ingest, Knowledge Assistant |

---

## Domain invariants

| Rule | Rationale |
|------|-----------|
| One generic SQL node (`domain.sql.query`) | Avoid N duplicate collectors; SQL lives in YAML/sources |
| `${EDIM_ENV}` scoping for FQNs | Prevent cross-env data leakage |
| Evidence rows may be **pack-preview** | Distinguish model citations from backfilled preview rows in RCA responses |

!!! warning "Live SQL on Apps"
    Domain SQL executes as the **signed-in user** on Databricks Apps. Verify [Access & permissions (C2b)](../platform/access-and-permissions.md) before debugging `OpenSession` failures.

---

## Summary

Start with **E1** for sources, then **E3b/E3c** for end-to-end product behavior.

**Next →** [Sources and SQL (E1)](sources-and-sql.md)
