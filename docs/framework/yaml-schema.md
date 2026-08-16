# YAML schema contract (BL-002)

**Learning path:** D1 · [Guide home](../README.md)
**← Previous:** [Retrieval & RAG](../platform/retrieval-and-rag.md) · **Next:** [YAML agents](yaml-agents.md) →


Canonical config contract for EDIM agents. Machine-readable schema:

`edim-dde-ai/schemas/agent.schema.json`

Validation runs during `parse_agent_definition` (structural) and optional JSON Schema checks for extended blocks.

---

## Required today

| Field | Type | Notes |
|-------|------|-------|
| `agent_id` | string | Stable id |
| `graph.nodes` | list | Non-empty; each has `id` + `type` |
| Graph entry | | `graph.entry` **or** a single `[START, node]` edge |

Also supported: `display_name`, `version` (int), `edges`, `conditional_edges` / `routes`, `content_dir`, inline `prompts` / `skills`.

---

## Extended blocks (R1 contract — optional keys)

**Optional key** = you may **omit the whole block** (or that field). Existing agents like `cluster_tuning` stay valid with only `agent_id` + `graph`. If you **do** include a key, its shape is validated.

| Omit entirely | Include with bad shape |
|---------------|------------------------|
| OK — no RAG / HITL / metadata required for R1 | Error — e.g. `metadata.risk_tier: extreme` |

```yaml
# Minimal (no optional extended blocks) — valid
agent_id: cluster_tuning
graph:
  nodes: [{ id: n1, type: passthrough }]
  edges: [[START, n1], [n1, END]]
```

```yaml
# Same agent + optional metadata — also valid
agent_id: cluster_tuning
metadata:
  owner: platform-team
  risk_tier: low
graph:
  nodes: [{ id: n1, type: passthrough }]
  edges: [[START, n1], [n1, END]]
```

Reserved extended blocks (shape checked when present):

```yaml
agent_id: example
version: 1
metadata:
  owner: platform-team
  risk_tier: low          # low | medium | high
  lifecycle: draft        # draft | review | approved | deprecated
  hitl_required: false    # catalog flag: “this agent needs human approval” (governance)

model:
  ref: foundry-gpt-4o     # logical id; resolves via env/registry later

# Optional: per-agent infra targets (omit → process .env globals).
# llm + search are wired; cosmos / sql-warehouse are shape-validated for demos.
bindings:
  llm:
    endpoint: ${ENV:AZURE_OPENAI_ENDPOINT}
    deployment: ${ENV:AZURE_OPENAI_DEPLOYMENT_NAME}
    temperature: 0.0
    top_p: 1.0
    top_k: 40
    max_tokens: 4096
  search:
    endpoint: ${ENV:EDIM_AZURE_SEARCH_ENDPOINT}
    index: ${ENV:EDIM_AZURE_SEARCH_INDEX}
  cosmos:
    endpoint: ${ENV:EDIM_COSMOS_ENDPOINT}
    database: ${ENV:EDIM_COSMOS_DATABASE}
  sql-warehouse:
    host: ${ENV:DATABRICKS_HOST}
    http_path: ${ENV:DATABRICKS_HTTP_PATH}

tools: []                 # future tool registry refs

rag:
  enabled: true
  corpus: spark-runbooks   # logical corpus (see corpora.yaml)
  top_k: 5
  search_mode: hybrid      # vector | keyword | hybrid
  cite: true               # require answers to reference retrieved doc ids / evidence refs

security:
  pii_redaction: true
  output_policy: null

evaluation:
  dataset: null           # LangSmith dataset name later

hitl:
  enabled: false          # runtime HITL workflow on/off (pause for human) — see below

graph:
  nodes: [...]
  edges: [...]
```

### `metadata.hitl_required` vs `hitl.enabled`

Two related fields on purpose (easy to confuse):

| Field | Layer | Meaning today |
|-------|--------|----------------|
| `metadata.hitl_required` | **Catalog / governance** | Declares that this agent *should* involve a human (inventory, risk, future gates). Synced into StateStore catalog. |
| `hitl.enabled` | **Runtime workflow** | Turns on HITL *behavior* in the run (pause / approve). Reserved for BL-039; not fully enforced in R1 graphs yet. |

Practical R1: set `metadata.hitl_required` for documentation/catalog; keep `hitl.enabled: false` until HITL runtime ships. Prefer not to set conflicting values (`hitl_required: true` + `enabled: false` means “policy says HITL needed, runtime not wired yet”).

### `rag.cite`

When `true`, the agent/prompt policy should **ground answers in retrieved sources** (runbook doc ids, evidence `ref`s) instead of free-form claims. Used on `spark_rca` with corpus `spark-runbooks`. It does not change the vector index itself — it is a **response policy** flag for prompts / future output checks.

### `bindings` (LLM + Search wired; cosmos / sql-warehouse documented)

Optional per-agent infra overrides. **Omit the whole block** (or omit a key) to keep process `.env` / Key Vault globals.

| Field | Meaning | Runtime today |
|-------|---------|---------------|
| `bindings.llm.endpoint` | Foundry / Azure OpenAI base URL | Injected into `llm_chain` |
| `bindings.llm.deployment` | Deployment / model name | Injected into `llm_chain` |
| `bindings.llm.temperature` | Sampling temperature (**literal**) | Injected; Foundry honors |
| `bindings.llm.top_p` | Nucleus sampling (**literal**) | Injected; Foundry honors |
| `bindings.llm.top_k` | Top-k (**literal**, provider-dependent) | Injected on config |
| `bindings.llm.max_tokens` | Max completion tokens (**literal**; sent as `max_completion_tokens`) | Injected; Foundry honors |
| `bindings.search.endpoint` | Azure AI Search service URL | Injected into `rag.retrieve` → `search_corpus` |
| `bindings.search.index` | Physical index name for this agent's retrieve nodes | Injected into `rag.retrieve` → `search_corpus` |
| `bindings.cosmos.endpoint` | Cosmos account URL | Parsed only (wiring later) |
| `bindings.cosmos.database` | Cosmos database name | Parsed only (wiring later) |
| `bindings.sql-warehouse.host` | Databricks workspace host | Parsed only (wiring later) |
| `bindings.sql-warehouse.http_path` | SQL warehouse HTTP path | Parsed only (wiring later) |

**Search binding notes**

- Applies to **`rag.retrieve`** nodes (guidance / runbooks). Experience-index searches via `search_corpus` in Python helpers still use process CORPUS_MAP unless you pass overrides in code.
- **Never** put the Search API key in YAML — key stays `EDIM_AZURE_SEARCH_KEY` / Key Vault.
- Omit → process `EDIM_AZURE_SEARCH_ENDPOINT` + CORPUS_MAP / `corpora.yaml` index mapping.

Use **literal strings** for non-secrets when you want (URLs, deployment names, index/database names, hosts) — e.g. `endpoint: https://….openai.azure.com/openai/v1`. Prefer `${ENV:VAR_NAME}` when the value is environment-specific and you do not want it committed. Sampling knobs (`temperature`, `top_p`, `top_k`, `max_tokens`) are always **literal numbers**.

**Never** put secrets in YAML (API keys, Cosmos keys, Search keys, client secrets) — those stay in `.env` / Key Vault and are read by the process globals (or via `${ENV:…}` only if you deliberately surface a secret-bearing env name, which is still discouraged in agent YAML).

If a `${ENV:…}` ref is declared but the variable is missing/empty, graph build **fails closed** for that LLM string binding.

Bundled agents ship a **commented** demo that reuses the live process env names (`AZURE_OPENAI_*`, `EDIM_AZURE_SEARCH_*`, `EDIM_COSMOS_*`, `DATABRICKS_*`).

```yaml
bindings:
  llm:
    endpoint: ${ENV:AZURE_OPENAI_ENDPOINT}
    deployment: ${ENV:AZURE_OPENAI_DEPLOYMENT_NAME}
    temperature: 0.0
    top_p: 1.0
    top_k: 40
    max_tokens: 4096
  search:
    endpoint: ${ENV:EDIM_AZURE_SEARCH_ENDPOINT}
    index: ${ENV:EDIM_AZURE_SEARCH_INDEX}
  cosmos:
    endpoint: ${ENV:EDIM_COSMOS_ENDPOINT}
    database: ${ENV:EDIM_COSMOS_DATABASE}
  sql-warehouse:
    host: ${ENV:DATABRICKS_HOST}
    http_path: ${ENV:DATABRICKS_HTTP_PATH}
```
---

## Breaking-change policy

1. Additive optional keys → minor schema version bump in docs
2. Removing/renaming required keys → major; provide migration notes
3. Existing R1 agents (`cluster_tuning`, `spark_rca`) remain valid without extended blocks

### What “freeze BL-002 in CI” means

**Freeze** = treat `schemas/agent.schema.json` as the R1 contract: stop casual edits; version/document changes.

**In CI** = add a pipeline (or `make`/pytest) step that loads every bundled `*.agent.yaml`, runs `validate_agent_dict(..., use_jsonschema=True)`, and **fails the build** if an agent drifts from the schema. That way a bad YAML cannot merge unnoticed.

Today: schema file + parse-time extended-block checks exist; **pytest gates** validate example agents (`edim-dde-ai/tests/test_example_agent_schema.py`) and bundled domain agents (`edim-dde-domain/tests/test_bundled_agent_schema.py`). Wire those tests into your PR CI (BL-045).

```bash
# From edim-dde-ai
make validate-schema
# or: pytest -q tests/test_example_agent_schema.py

# From edim-dde-domain
pytest -q tests/test_bundled_agent_schema.py
```

---

## CLI / library

### Python

```python
from pathlib import Path
import yaml
from edim_dde_ai.schema.validate import validate_agent_dict

data = yaml.safe_load(Path("path/to/agent.agent.yaml").read_text())
validate_agent_dict(data)                       # extended blocks
validate_agent_dict(data, use_jsonschema=True)  # + JSON Schema (needs jsonschema extra)
```

### `edim-dde-ai` CLI (from `edim-dde-ai` package)

```bash
cd /path/to/edim/edim-dde-ai
pip install -e ".[dev,schema]"   # schema extra pulls jsonschema

edim-dde-ai version

# Structural validate one YAML
edim-dde-ai validate examples/agents/echo_agent.agent.yaml

# Domain bundled agents (from domain tree)
edim-dde-ai validate \
  ../edim-dde-domain/src/edim_dde_domain/agents/cluster_tuning/cluster_tuning.agent.yaml
edim-dde-ai validate \
  ../edim-dde-domain/src/edim_dde_domain/agents/spark_rca/spark_rca.agent.yaml

# Register + list + run a sample agent
edim-dde-ai register examples/agents/echo_agent.agent.yaml
edim-dde-ai register-dir examples/agents
edim-dde-ai list
edim-dde-ai run echo_agent --input '{"message":"hi"}'
```

Structural parse remains the source of truth for graph connectivity; JSON Schema covers metadata/extended blocks.

<!-- edim-learning-nav -->
---

← [Retrieval & RAG](../platform/retrieval-and-rag.md) · [Guide home](../README.md) · [YAML agents](yaml-agents.md) →
