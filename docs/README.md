# EDIM DDE documentation

Engineer guide for the **EDIM DDE** stack: YAML-driven LangGraph agents, domain SQL/auth, and a thin FastAPI host.

Inspired by product docs such as [Databricks](https://docs.databricks.com/aws/en/), [Azure Data Factory](https://learn.microsoft.com/en-us/azure/data-factory/), [Apache Airflow](https://airflow.apache.org/docs/), and lifecycle references like [EMR Serverless job states](https://docs.aws.amazon.com/emr/latest/EMR-Serverless-UserGuide/job-states.html).

## Packages

| Package | Role |
|---------|------|
| [`edim-dde-ai`](../../edim-dde-ai/) | Framework: YAML → LangGraph, registries, `llm_chain`, routers |
| [`edim-dde-domain`](../) | Platform + product agents: sources, SQL, auth, Foundry, bundled RCA/tuning |
| [`edim-dde-api`](../../edim-dde-api/) | HTTP: CORS, Apps token middleware, `/api/v1/*` |

> **Temporary home:** This engineer hub lives under `edim-dde-domain/docs/` until a parent `edim` repo exists. Move the tree later if needed.

## Get started

- [Quickstart](getting-started/quickstart.md) — install, run API, call an endpoint
- [Core concepts](getting-started/concepts.md) — agent, node, state, content, bootstrap

## Explore

- [Architecture overview](architecture/overview.md)
- [Packages](architecture/packages.md)
- [Auth and SQL](architecture/auth-and-sql.md)
- [Request flow](architecture/request-flow.md)

## Build

- [Agent package layout](build-agents/agent-package-layout.md)
- [New agent step-by-step](build-agents/step-by-step.md)
- [External plugins](build-agents/external-plugins.md)

## Framework (`edim-dde-ai`)

- [YAML agents](framework/yaml-agents.md)
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
- [Backlog](../../BACKLOG.md) — living handoff and open work (workspace root)

## Deep dives (package docs)

- [edim-dde-ai DESIGN](../../edim-dde-ai/docs/DESIGN.md) · [USAGE](../../edim-dde-ai/docs/USAGE.md)
- [Domain sources & SQL design](DESIGN_SOURCES_AND_SQL_NODES.md)
