# EDIM DDE — Release 1 reference architecture

**Status:** Phase 0 / BL-001 — ready for first sign-off  
**Audience:** Architecture review and PowerPoint export  
**Version:** R1 (`1.0.0` package baseline)

This document is the **approved reference map** for the EDIM AI agent stack: packages, trust boundaries, request flow, environments, and R1 non-goals.

---

## Sign-off

| Role | Name | Date | Decision |
|------|------|------|----------|
| First sign-off | _(you)_ | TBD | Approve R1 architecture for Phase 0 |

Update this table when you formally approve.

---

## Presentation assets (PPT)

| Asset | Path | Use |
|-------|------|-----|
| **HTML slide deck (8 slides)** | [diagrams/r1-architecture-deck.html](diagrams/r1-architecture-deck.html) | Open in Chrome → **Present** → screenshot each 1280×720 slide into PPT |
| System context SVG | [diagrams/r1-system-context.svg](diagrams/r1-system-context.svg) | Insert into PPT as vector (preferred over PNG) |
| Request sequence SVG | [diagrams/r1-request-sequence.svg](diagrams/r1-request-sequence.svg) | Insert into PPT as vector |
| Environment deploy SVG | [diagrams/r1-environments.svg](diagrams/r1-environments.svg) | Insert into PPT as vector |

**How to build the PPT quickly**

1. Open the HTML deck in Chrome (allows Simple Icons CDN for brand marks).
2. Click **Present** (fullscreen) and capture slides 01–08.
3. For the three detailed diagrams, prefer **Insert → Picture → SVG** from the files above (crisper in Zoom/print).
4. Icons in the HTML deck use [Simple Icons](https://simpleicons.org/) (Databricks, Azure, LangChain, FastAPI). For final Marketing brand packs, swap logos if required.

---

## 1. System context

```text
┌────────────────────┐     HTTPS      ┌──────────────────────────────────────┐
│  Clients           │───────────────►│  edim-dde-api (FastAPI)               │
│  • curl / Postman  │                │  • CORS                              │
│  • Databricks Apps │                │  • User token middleware             │
│  • Future UI       │                │  • Request id                        │
└────────────────────┘                │  • Key Vault secret bootstrap        │
                                      └───────────────┬──────────────────────┘
                                                      │ create_agent().invoke
                                      ┌───────────────▼──────────────────────┐
                                      │  edim-dde-ai (YAML → LangGraph)      │
                                      │  • Agent / node / router registries  │
                                      │  • Content hub (prompts / skills)    │
                                      │  • LangSmith tracing (optional)      │
                                      │  • invoke_agent (subgraph spike)     │
                                      └───────────────┬──────────────────────┘
                         ┌────────────────────────────┼────────────────────────────┐
                         │                            │                            │
               ┌─────────▼─────────┐      ┌───────────▼──────────┐     ┌──────────▼──────────┐
               │ edim-dde-domain   │      │ Azure AI Foundry     │     │ LangSmith           │
               │ • sources.yaml    │      │ (Azure OpenAI)       │     │ SDBX / DEV / PROD   │
               │ • domain.sql.query│      │ LLM completions      │     │ traces / evals      │
               │ • PII redaction   │      └──────────────────────┘     └─────────────────────┘
               │ • cluster_tuning  │
               │ • spark_rca       │
               └─────────┬─────────┘
                         │ Databricks SQL connector + AAD
               ┌─────────▼─────────┐
               │ Databricks        │
               │ • SQL Warehouse   │
               │ • Unity Catalog   │
               └───────────────────┘
```

**Trust boundaries**

| Boundary | What crosses it | Auth |
|----------|-----------------|------|
| Client → API | JSON over HTTPS | Apps gateway / network; CORS allow-list |
| API → SQL | Queries via `domain.sql.query` | Apps: `X-Forwarded-Access-Token`; local: `az login` |
| API → Foundry | Chat completions | Local: `az login`; PROD: SP from Key Vault |
| Runtime → LangSmith | Traces (redacted) | `LANGCHAIN_API_KEY` / project per env |

---

## 2. Package responsibilities

| Package | Version | Responsibility |
|---------|---------|----------------|
| **edim-dde-ai** | 1.0.0 | YAML schema, LangGraph builder, registries, `llm_chain`, `invoke_agent`, LangSmith hooks, PII helpers (shared) |
| **edim-dde-domain** | 1.0.0 | Named SQL sources, auth, Foundry adapter, Key Vault load, bundled agents, domain PII patterns |
| **edim-dde-api** | 1.0.0 | HTTP surface, CORS, token middleware, lifespan bootstrap, `/api/v1/*` |

Dependency direction: `api` → `domain` → `ai`.

---

## 3. R1 non-goals (explicit)

Deferred past Release 1 / Phase 0:

- Full MCP connector mesh (ADO / ServiceNow / JIRA)
- Enterprise RAG / Azure AI Search platform
- HITL review UI
- Governance dashboard / risk questionnaires
- Enforced RBAC roles beyond current identity paths (role **matrix is documented**; enforcement is later)

---

## 4. Logical request flow (detail)

See also [request-flow.md](request-flow.md) and the sequence SVG.

```text
Client
  │  POST /api/v1/recommendations  (+ X-Request-Id optional)
  ▼
API middleware
  │  Bind Databricks user token (Apps)
  │  Ensure request_id
  ▼
Route handler
  │  Validate body (Pydantic)
  │  asyncio.to_thread(create_agent("cluster_tuning").invoke, state, config=…)
  ▼
edim-dde-ai MetadataAgent
  │  Wrap flat state → LangGraph data bag
  │  LangSmith run tags: agent_id, env, request_id
  ▼
YAML graph nodes
  │  domain.sql.query → sources.resolve → auth token → warehouse → UC Delta
  │  domain.tuning.*  → sizing / guardrails / risk
  │  llm_chain        → ContentHub prompts + Foundry
  │  (optional) invoke_agent → nested agent with depth limit
  ▼
Response projection
  │  Map agent state → TuningResponse / RcaResponse (never dump full state)
  ▼
Client + LangSmith (trace retained per project retention)
```

---

## 5. Environments (Phase 0 focus)

Full set later: **SDBX, DEV, UAT, INTG, PROD**.  
**Phase 0 focus:** SDBX, DEV, PROD — see [environments.md](../platform/environments.md).

| Env | Purpose | LangSmith project (convention) |
|-----|---------|--------------------------------|
| SDBX | Sandbox / spikes | `edim-dde-sdbx` |
| DEV | Active development | `edim-dde-dev` |
| PROD | Production | `edim-dde-prod` |

---

## 6. Security stance (R1)

| Control | R1 behavior |
|---------|-------------|
| YAML code execution | **Denied** — node/router types must be pre-registered |
| SQL identity | Apps user OAuth or local Azure AD |
| LLM identity | Azure AD / SP from Key Vault |
| Secrets | Azure Key Vault SDK bootstrap into process env |
| PII | Expandable redaction patterns (SSN, PAN, account, member id) before logs/traces |
| Roles | Documented matrix; **not enforced** in Phase 0 beyond identity above |

Details: [security-baseline.md](../platform/security-baseline.md), [pii-guardrails.md](../platform/pii-guardrails.md).

---

## 7. Observability (LangSmith)

Phase 0 documents setup and wires optional tracing. Full eval/CI is Phase 2+.

Guide: [langsmith-setup.md](../platform/langsmith-setup.md).

---

## Related docs

- [Architecture overview](overview.md)
- [Packages](packages.md)
- [Auth and SQL](auth-and-sql.md)
- [Config → observability flow](config-to-observability.md)
- [YAML schema contract](../framework/yaml-schema.md)
- [Orchestration topology](../framework/orchestration-topology.md)
