# Preface

**EDIM DDE Engineer Guide** · Release R1 (`1.0.0`)

This document is the authoritative engineering guide for the EDIM DDE stack: a YAML-driven LangGraph agent platform for data platform reliability, delivered as three Python packages and a thin FastAPI host.

---

## About this book

### Scope

This guide explains **what EDIM DDE is**, **how it is architected**, and **how to operate, extend, and deploy it**. It targets engineers who must:

- Run and validate the API on a laptop, in Docker, or on Databricks Apps.
- Author or modify YAML agents and domain node types.
- Wire platform planes (SQL auth, Foundry, Key Vault, observability, persistence, retrieval).

It does **not** replace product backlog or enterprise roadmap documents (`BACKLOG.md`, `AI_Framework_Platform_Capability_Backlog.md` at workspace root).

### Organization

The guide follows eight **parts** (A–H), ordered as a learning path:

| Part | Title | Purpose |
|------|-------|---------|
| **A** | Start here | Orientation, quickstart, vocabulary |
| **B** | Architecture | System design, planes, request flow |
| **C** | Platform | Security, envs, stores, RAG, tracing |
| **D** | Framework | YAML schema, nodes, orchestration, HITL |
| **E** | Domain | SQL sources, bundled agents, walkthroughs |
| **F** | Build agents | Authoring handbook for new agents |
| **G** | API host | Configuration, endpoints, deployment |
| **H** | Reference | Env catalog, glossary, smoke, packaging |

Each part opens with a **chapter overview** page. Sequential readers should use sidebar **Previous / Next** navigation or the [Guide map](getting-started/guide-map.md).

### Conventions

| Convention | Meaning |
|------------|---------|
| **Monospace** | Code, env vars, paths, HTTP routes (`EDIM_ENV`, `/api/v1/rca/analyze`) |
| **must / should / may** | **must** = required · **should** = recommended · **may** = optional |
| **R1** | Current release scope; items marked *design only* or *parked* are not implemented |
| **Plane** | Cross-cutting concern with swappable backend (control, knowledge, data, observability) |

!!! tip "Pro tip"
    Bookmark [Environment variables](reference/env-vars.md) and [Glossary](reference/glossary.md) while reading Parts B–G.

---

## Naming

| Term | Stands for | Organizational context |
|------|------------|-------------------------|
| **EDIM** | **E**nterprise **D**ata & **I**nformation **M**anagement | Program under the **Enterprise Data & Analytics** portfolio (or services) |
| **DDE** | **D**igital **D**ata **E**ngineering | Engineering unit under the **Digital** business unit |
| **EDIM DDE** (this stack) | EDIM capabilities delivered by DDE | Software platform: `edim-dde-ai`, `edim-dde-domain`, `edim-dde-api` |

Repository and package names use the **`edim-dde-*`** prefix (EDIM program, DDE engineering unit).

---

## What is EDIM DDE?

**EDIM DDE** is a **YAML-driven LangGraph agent platform** built by **Digital Data Engineering (DDE)** for the **Enterprise Data & Information Management (EDIM)** program. Declarative graphs in `*.agent.yaml` compile into LangGraph runtime objects and are exposed through **`edim-dde-api`**.

**Bundled product agents (R1):**

| Agent | Purpose |
|-------|---------|
| **`cluster_tuning`** | Recommend Databricks cluster sizing from job telemetry |
| **`spark_rca`** | Diagnose Spark job failures using metrics, logs, and runbooks |

The same runtime supports **additional agents** without forking the host: register node types, add YAML, bootstrap, and optionally bind HTTP routes.

---

## Design intent

Enterprise data platforms repeatedly implement the same pipeline: collect telemetry from Unity Catalog, apply domain logic, invoke an LLM with guardrails, persist audit metadata, and return operator-facing results. EDIM DDE codifies that pipeline as **declarative graphs** with explicit plane boundaries.

| Problem | EDIM approach |
|---------|---------------|
| Ad hoc notebooks and scripts | Version-controlled `*.agent.yaml` graphs |
| Unsafe YAML extensibility | Allowlisted node `type` ids + registries |
| Coupled product and transport | `api` → `domain` → `ai` package split |
| Environment bleed | One process per `EDIM_ENV`; no cross-env SQL |
| Secret sprawl | Key Vault bootstrap; Apps user token for SQL |

**Source-of-truth rule:** Git holds graphs and prompt content. StateStore holds catalog and sessions. Vector indexes hold knowledge chunks. None of these replace graph routing logic in R1.

---

## The three packages

```text
edim-dde-api     REST host, middleware, lifespan, /api/v1
       │
       ▼
edim-dde-domain  sources.yaml, SQL, auth, Foundry, bundled agents
       │
       ▼
edim-dde-ai      YAML → LangGraph, registries, builtins, planes
```

| Package | Responsibility |
|---------|------------------|
| **`edim-dde-ai`** | Graph compilation, node/router registries, LLM and plane abstractions |
| **`edim-dde-domain`** | Platform wiring, `domain.sql.query`, product agent implementations |
| **`edim-dde-api`** | HTTP surface, Databricks Apps token middleware, bootstrap orchestration |

Install sibling repositories adjacent to one another. Dependency direction is **`api` → `domain` → `ai`**.

---

## Who should read this guide

| Reader | Primary parts |
|--------|---------------|
| **Platform / DevOps engineer** | A, C, G, H |
| **Agent author / data engineer** | A, D, E, F |
| **API consumer / SRE** | A, G, H |
| **Architect / reviewer** | A, B, H3 |

No prior LangGraph experience is required for Part A. Part B assumes you completed [Core concepts (A2)](getting-started/concepts.md).

---

## How to read sequentially

**First-time path (recommended):**

1. [Guide map (A0)](getting-started/guide-map.md) — full table of contents  
2. [Quickstart (A1)](getting-started/quickstart.md) — runnable stack  
3. [Core concepts (A2)](getting-started/concepts.md) — vocabulary  
4. [Part B — Architecture](architecture/index.md) → [End-to-end design (B1)](architecture/end-to-end-design.md)  
5. Branch by role using the Guide map  

---

## System model

```text
┌──────────── SOURCE CONTROL (Git) ───────────────────────────┐
│  *.agent.yaml · prompts · skills · runbooks · corpora       │
└────────────────────────────┬────────────────────────────────┘
                             │ bootstrap
     ┌───────────────────────┼───────────────────────┐
     ▼                       ▼                       ▼
 CONTROL PLANE          KNOWLEDGE PLANE          DATA PLANE
 StateStore             RetrievalProvider        LangGraph + SQL + LLM
     │                       │                       │
     └───────────────────────┼───────────────────────┘
                             ▼
                    OBSERVABILITY PLANE
                    LangSmith / MLflow
```

---

## Building this guide locally

MkDocs Material renders this book at `http://127.0.0.1:8080/guide/`:

```bash
cd edim-dde-api
make guide-site && make compose-up
```

Source files live under `edim-dde-domain/docs/`. Contributors: see [Documentation style](contribute/documentation-style.md).

---

## Document control

| Field | Value |
|-------|-------|
| **Release** | R1 / `1.0.0` |
| **Primary audience** | Platform engineers, agent authors, API operators |
| **Navigation** | [Guide map (A0)](getting-started/guide-map.md) |

**Begin →** [Guide map](getting-started/guide-map.md) · [Quickstart (A1)](getting-started/quickstart.md)
