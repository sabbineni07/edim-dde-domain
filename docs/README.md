# EDIM DDE documentation

Engineer guide for the **EDIM DDE** stack: YAML-driven LangGraph agents, domain SQL/auth, and a thin FastAPI host.

**Release:** R1 / `1.0.0` (Phase 0 foundation)

Inspired by product docs such as [Databricks](https://docs.databricks.com/aws/en/), [Azure Data Factory](https://learn.microsoft.com/en-us/azure/data-factory/), [Apache Airflow](https://airflow.apache.org/docs/), and lifecycle references like [EMR Serverless job states](https://docs.aws.amazon.com/emr/latest/EMR-Serverless-UserGuide/job-states.html).

## Packages

| Package | Role |
|---------|------|
| [`edim-dde-ai`](../../edim-dde-ai/) | Framework: YAML → LangGraph, registries, `llm_chain`, `invoke_agent`, observability + state store |
| [`edim-dde-domain`](../) | Platform + product agents: sources, SQL, auth, Foundry, Key Vault, PII, bundled RCA/tuning |
| [`edim-dde-api`](../../edim-dde-api/) | HTTP: CORS, Apps token middleware, KV bootstrap, `/api/v1/*` |

> **Temporary home:** This engineer hub lives under `edim-dde-domain/docs/` until a parent `edim` repo exists. Move the tree later if needed.

## Get started

- [Quickstart](getting-started/quickstart.md) — install, run API, call an endpoint
- [Core concepts](getting-started/concepts.md) — agent, node, state, content, bootstrap
- [LangSmith setup](platform/langsmith-setup.md) — tracing for SDBX / DEV / PROD

## Architecture (R1)

- [**Reference architecture (sign-off + PPT)**](architecture/reference-architecture.md)
- [Architecture deck (HTML + brand icons)](architecture/diagrams/r1-architecture-deck.html)
- [Overview](architecture/overview.md)
- [Packages](architecture/packages.md)
- [Auth and SQL](architecture/auth-and-sql.md)
- [Request flow](architecture/request-flow.md)
- [Config → observability](architecture/config-to-observability.md)

## Platform (Phase 0)

- [Environments (SDBX / DEV / PROD)](platform/environments.md)
- [**Control-plane state store** (Postgres / Cosmos / Redis)](platform/state-store.md)
- [**Retrieval & RAG** (FAISS / Azure AI Search / Databricks)](platform/retrieval-and-rag.md)
- [Observability providers (LangSmith / MLflow)](platform/observability.md)
- [Security baseline & role matrix](platform/security-baseline.md)
- [PII guardrails](platform/pii-guardrails.md)
- [LangSmith setup](platform/langsmith-setup.md)

## Build

- [Agent package layout](build-agents/agent-package-layout.md)
- [New agent step-by-step](build-agents/step-by-step.md)
- [External plugins](build-agents/external-plugins.md)

## Framework (`edim-dde-ai`)

- [YAML agents](framework/yaml-agents.md)
- [YAML schema contract](framework/yaml-schema.md)
- [Orchestration topology (`invoke_agent`)](framework/orchestration-topology.md)
- [Nodes and routers](framework/nodes-and-routers.md)
- [Content and LLM](framework/content-and-llm.md)
- [Conditional edges](framework/conditional-edges.md)

## Domain & API

- [Sources and SQL](domain/sources-and-sql.md)
- [Bundled agents](domain/bundled-agents.md)
- [HTTP endpoints](api/endpoints.md)
- [Configuration](api/configuration.md)

## Reference

- [Environment variables](reference/env-vars.md)
- [Node type ids](reference/node-type-ids.md)
- [Glossary](reference/glossary.md)

## Contribute

- [Testing](contribute/testing.md)
- [Product backlog](../../BACKLOG.md) — day-to-day EDIM handoff
- [Platform capability backlog](../../AI_Framework_Platform_Capability_Backlog.md) — phased enterprise roadmap

## Deep dives (package docs)

- [edim-dde-ai DESIGN](../../edim-dde-ai/docs/DESIGN.md) · [USAGE](../../edim-dde-ai/docs/USAGE.md)
- [Domain sources & SQL design](DESIGN_SOURCES_AND_SQL_NODES.md)
