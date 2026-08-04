# End-to-end design (architecture, flow, patterns)

**Learning path:** B1 · [Guide home](../README.md)  
**← Previous:** [Core concepts](../getting-started/concepts.md) · **Next:** [Architecture overview](overview.md) →

This is the **master design page** for EDIM DDE. Read it once end-to-end; use sibling pages for depth. It answers: *what are the planes, how does one request flow, which GoF patterns we use, and where code lives.*

---

## 1. Purpose and hybrid model

EDIM DDE is a **YAML-driven LangGraph agent platform** for FinTech reliability use cases (Spark RCA, cluster tuning), hosted as a thin FastAPI app on Databricks Apps / local.

| Layer | Responsibility | Must not |
|-------|----------------|----------|
| **YAML** (`*.agent.yaml`) | Topology: nodes, edges, optional `rag` / `metadata` / policy blocks | Import arbitrary Python; execute code |
| **Python node types** | Allowlisted `type` → factory → `(state) -> partial updates` | Appear as free-form import paths in YAML |
| **Providers** | Pluggable backends (LLM, observability, state store, retrieval) | Be hard-coded into every agent |

```text
*.agent.yaml  ──parse/validate──► AgentDefinition
                                      │
                                      ▼
                              GraphBuilder (Builder)
                                      │
                         registries resolve type ids (Registry + Strategy)
                                      │
                                      ▼
                              MetadataAgent.invoke(state)   (Template Method)
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
              SQL / domain      rag.retrieve        llm_chain
              nodes             (Retrieval)         (LLMProvider)
```

---

## 2. Planes (system design)

Keep these planes separate — they solve different problems and use different storage.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ SOURCE CONTROL                                                          │
│  Azure DevOps / Git: *.agent.yaml, prompts, skills, runbooks, CI        │
│  SoT for graphs and content artifacts                                   │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│ CONTROL PLANE                                                           │
│  StateStore: agent catalog metadata, sessions, audit                    │
│  Backends: memory | postgres (local) | cosmos (deployed) | redis        │
│  Pattern: Strategy + Protocol                                           │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│ KNOWLEDGE / RETRIEVAL PLANE                                             │
│  RetrievalProvider: similarity / hybrid search hits                     │
│  Backends: none | memory | faiss | azure_ai_search | databricks_vector  │
│  RAG = retrieve + inject prompt + LLM (graph pattern, not a backend)    │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│ DATA PLANE                                                              │
│  LangGraph execution, domain.sql.query → Databricks UC, Foundry LLM     │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│ OBSERVABILITY PLANE                                                     │
│  ObservabilityProvider: langsmith | mlflow | none                       │
│  Side channel — does not own business state                             │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│ INGEST PLANE (batch)                                                    │
│  Platform Jobs: chunk → embed → write index                             │
│  Curated path: POST /api/v1/knowledge/ingest (Acceptance-gated)         │
└─────────────────────────────────────────────────────────────────────────┘
```

| Artifact | Plane | SoT |
|----------|-------|-----|
| Graph YAML | Source control | Git |
| Prompt / skill markdown | Source control | Git |
| Agent owner / lifecycle / git_sha | Control plane | StateStore (synced at bootstrap) |
| Runbook chunks / embeddings | Knowledge | FAISS file / Azure index / VS index |
| Job metrics / logs | Data | Unity Catalog tables |
| Traces | Observability | LangSmith / MLflow |

---

## 3. Package map and dependency rule

```text
edim-dde-api
    │  depends on
    ▼
edim-dde-domain
    │  depends on
    ▼
edim-dde-ai
```

| Package | Owns | Does not own |
|---------|------|--------------|
| **edim-dde-ai** | YAML→graph, registries, builtins (`llm_chain`, `invoke_agent`, `rag.retrieve`), provider protocols | Product SQL, HTTP DTOs, Databricks auth |
| **edim-dde-domain** | `sources.yaml`, `domain.sql.query`, Foundry adapter, Key Vault, PII, bundled agents, `corpora.yaml`, runbooks | FastAPI routes |
| **edim-dde-api** | Middleware, lifespan wiring, OpenAPI projection, curated ingest route | Agent business logic |

Detail: [packages.md](packages.md).

---

## 4. GoF and related patterns (with examples)

We deliberately use a **small** pattern set (see also package [DESIGN.md](../../../edim-dde-ai/docs/DESIGN.md)).

### 4.1 Registry (catalog) + Singleton scope

**Where:** `registry/base.py`, agent/node/chain/router registries; process-wide provider holders for observability / store / retrieval.

**Why:** One keyed catalog per concern; tests clear/restore between cases.

```python
# Strategy selected by allowlisted id (not by import path in YAML)
from edim_dde_ai import register_node

@register_node("domain.rca.classify_failure")
def classify_failure_factory(_config: dict):
    def _node(state: dict) -> dict:
        ...
    return _node
```

YAML only references the id:

```yaml
- id: rule_classify
  type: domain.rca.classify_failure
```

### 4.2 Strategy

**Where:** node factories, router factories, chain invokers, `ObservabilityProvider`, `StateStore`, `RetrievalProvider`, `LLMProvider`.

**Why:** Swap algorithms (Postgres vs Cosmos, FAISS vs Azure Search, LangSmith vs MLflow) without rewriting agents.

```bash
# Same spark_rca YAML — different retrieval Strategy via env
EDIM_RETRIEVAL=faiss
# vs
EDIM_RETRIEVAL=azure_ai_search
```

```python
from edim_dde_ai.retrieval import configure_retrieval_from_env, search_corpus
configure_retrieval_from_env()          # Strategy from EDIM_RETRIEVAL
hits = search_corpus("OOM", corpus="spark-runbooks")
```

### 4.3 Builder

**Where:** `graph/builder.py` → `GraphBuilder` → `build_graph(definition)`.

**Why:** Stepwise assembly: add nodes → entry → edges → conditional edges → compile.

```text
AgentDefinition
  → GraphBuilder.add_nodes()
  → set_entry()
  → add_edges()
  → add_conditional_edges()
  → compile() → LangGraph
```

### 4.4 Factory Method

**Where:** `factories/agent.py` — `AgentFactory.create(agent_id)` / `create_agent()`.

**Why:** Construct a ready `MetadataAgent` from a registered definition (compile once, cache).

```python
from edim_dde_ai import create_agent
agent = create_agent("spark_rca")
final = agent.invoke({"job_run_id": "jr-1", "evidence_pack": {...}})
```

### 4.5 Adapter

**Where:** `graph/adapters.py` — flat `dict` node callables ↔ LangGraph `AgentState.data` bag.

**Why:** Authors write simple `(state) -> partial`; LangGraph sees a typed channel.

### 4.6 Template Method

**Where:** `graph/runtime.py` — `MetadataAgent.invoke` / `ainvoke` share `_prepare` / `_extract`.

**Why:** Uniform invoke surface + observability config merge for every agent.

### 4.7 Facade

**Where:** `edim_dde_ai.__init__`, `api/entrypoints.py`, API routes.

**Why:** Stable public API over registries, builders, and providers.

```python
from edim_dde_ai import (
    register_from_yaml,
    create_agent,
    configure_observability_from_env,
    configure_state_store_from_env,
    configure_retrieval_from_env,
)
```

### 4.8 Protocol (typing / structural)

**Where:** `ObservabilityProvider`, `StateStore`, `RetrievalProvider`, `LLMProvider`, …

**Why:** Duck-typed backends with clear method contracts; optional extras install real clients.

---

## 5. API lifespan sequence (startup)

Matches **Part C** of the guide — configure planes before serving traffic:

```text
1. Key Vault bootstrap          (optional secrets → env)
2. configure_observability_from_env()   # EDIM_OBSERVABILITY
3. configure_state_store_from_env()     # EDIM_STATE_STORE
4. configure_retrieval_from_env()       # EDIM_RETRIEVAL
5. bootstrap_agents()
      · load sources.yaml
      · load corpora.yaml
      · import agents/*/nodes.py
      · register *.agent.yaml
      · external plugins (EDIM_AGENT_DIRS)
6. sync_registered_agents_to_store()    # catalog metadata upsert + audit
7. set_llm_provider(lazy Foundry)
8. ready — GET /health reports observability, state_store, retrieval
```

Failures configuring store/retrieval/observability **log and continue** with safe defaults (`memory` / `none`) so `/health` remains available.

---

## 6. Request lifecycle (data plane)

Example: `POST /api/v1/rca/analyze`

```text
Client
  │  JSON + optional X-Request-Id / Apps token
  ▼
Middleware
  │  Bind Databricks user token (Apps)
  │  Ensure request_id
  ▼
Route
  │  Pydantic RcaRequest
  │  build_run_config(agent_id, request_id)  → observability tags
  │  asyncio.to_thread(create_agent("spark_rca").invoke, …)
  ▼
MetadataAgent (Template Method)
  │  Wrap flat state → LangGraph data bag
  ▼
YAML graph
  │  domain.sql.query × N     → UC telemetry (skip if evidence_pack override)
  │  assemble_evidence
  │  classify_failure
  │  build_retrieval_query
  │  rag.retrieve             → Knowledge plane (may be empty)
  │  prepare_llm_payload      → inject runbook_context
  │  llm_chain (rca)          → Foundry
  │  parse / validate
  ▼
RcaResponse projection        (never dump full state bag)
  + LangSmith/MLflow trace    (side channel)
```

Tuning (`/api/v1/recommendations`) is the same host pattern without the retrieval pilot.

Sequence SVG: [r1-request-sequence.svg](diagrams/r1-request-sequence.svg) · Narrative: [request-flow.md](request-flow.md).

---

## 7. Similarity search vs RAG (knowledge design)

```text
RetrievalProvider.search(query) ──► hits[]     ← similarity / hybrid search
        │
        ▼
agent graph injects hits into prompt ──► LLM   ← RAG pattern
```

| | Similarity search | RAG |
|--|-------------------|-----|
| Output | Ranked chunks | Answer + (optional) citations |
| LLM? | No | Yes |
| EDIM home | `RetrievalProvider` + `rag.retrieve` | Graph: retrieve → `llm_chain` |
| Pilot | — | `spark_rca` runbook grounding |

**Deployed default:** Azure AI Search · **Local / Volume:** FAISS · **Override:** per corpus in `corpora.yaml`.  
Full detail: [retrieval-and-rag.md](../platform/retrieval-and-rag.md).

---

## 8. Control plane vs knowledge vs UC

| Need | Use |
|------|-----|
| “Which agents are approved?” | StateStore catalog |
| “Resume HITL session” | StateStore sessions |
| “Similar OOM playbook” | RetrievalProvider |
| “CPU% for job run” | `domain.sql.query` → UC |

Do **not** put embeddings in Cosmos/Postgres StateStore, or agent YAML in the vector index.

---

## 9. Security stance (R1)

| Control | Behavior |
|---------|----------|
| YAML code execution | **Denied** — pre-registered types only |
| SQL identity | Apps OAuth token or local `az login` |
| LLM identity | Azure AD / SP (Key Vault in PROD) |
| Secrets | Key Vault bootstrap into env (no overwrite) |
| PII | Expandable redaction before logs/traces |
| Roles | Documented matrix; enforcement later |

→ [security-baseline.md](../platform/security-baseline.md) · [pii-guardrails.md](../platform/pii-guardrails.md) · [auth-and-sql.md](auth-and-sql.md)

---

## 10. Environment matrix (Phase 0)

| Concern | SDBX / local | DEV | PROD |
|---------|--------------|-----|------|
| `EDIM_ENV` | `sdbx` | `dev` | `prod` |
| State store | postgres / memory | postgres | **cosmos** |
| Retrieval | faiss (local or Volume) | faiss / Azure | **azure_ai_search** |
| Observability | LangSmith project per env | same | same + PII |

→ [environments.md](../platform/environments.md)

---

## 11. Presentation assets

| Asset | Use |
|-------|-----|
| [Reference architecture](reference-architecture.md) | Sign-off table + narrative |
| [HTML deck](diagrams/r1-architecture-deck.html) | PPT screenshots |
| [System context SVG](diagrams/r1-system-context.svg) | Vector insert |
| [Request sequence SVG](diagrams/r1-request-sequence.svg) | Sequence |
| [Environments SVG](diagrams/r1-environments.svg) | Deploy view |

---

## 12. Where to go next

Continue the path:

1. [Architecture overview](overview.md) — compact sketch  
2. [Packages](packages.md) — ownership  
3. [Reference architecture](reference-architecture.md) — sign-off  
4. Then Part C platform docs starting at [Environments](../platform/environments.md)

---

← [Core concepts](../getting-started/concepts.md) · [Guide home](../README.md) · [Architecture overview](overview.md) →
