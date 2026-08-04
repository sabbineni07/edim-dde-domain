# Retrieval, similarity search, and RAG (BL-021)

This guide explains **similarity search vs RAG**, the pluggable **`RetrievalProvider`** backends (FAISS · Azure AI Search · Databricks Vector Search), how **`spark_rca`** uses runbook grounding, and how engineers operate local vs deployed indexes.

---

## 1. Concepts (read this first)

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ SIMILARITY / HYBRID SEARCH  — RetrievalProvider                          │
│   Input: query (+ corpus, top_k, mode)                                   │
│   Output: ranked hits {id, text, score, metadata, source}                │
│   Does NOT call an LLM                                                   │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ used by agent graph
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ RAG (pattern)  — retrieve → inject into prompt → llm_chain → answer      │
│   Pilot: spark_rca runbook grounding                                     │
└──────────────────────────────────────────────────────────────────────────┘
```

| Term | Meaning |
|------|---------|
| **Similarity search** | Find nearest / best-matching chunks (vector and/or keyword) |
| **Hybrid search** | Combine vector + keyword signals (`search_mode: hybrid`) |
| **RAG** | Application pattern that **uses** retrieval, then an LLM |
| **Corpus** | Logical knowledge set (e.g. `spark-runbooks`) — not a backend name |

**Design rule (same as StateStore / Observability):** backends are plug-and-play; agent YAML composes the RAG recipe.

---

## 2. Decisions locked for EDIM

| Decision | Choice |
|----------|--------|
| Deployed default | **Azure AI Search** (`EDIM_RETRIEVAL=azure_ai_search`) |
| Local / Volume | **FAISS** file index under `EDIM_FAISS_INDEX_PATH` (local **or** Databricks Volume) |
| Per-corpus override | Optional in `corpora.yaml` (e.g. Databricks VS for a lakehouse corpus) |
| First pilot | **`spark_rca`** runbook grounding (not cluster_tuning) |
| Bulk ingest | **Platform team Jobs** |
| Curated ingest | **`POST /api/v1/knowledge/ingest`** with `accepted=true` + optional user `summary` |

---

## 3. Planes (where things live)

| Plane | Responsibility |
|-------|----------------|
| **Source control** | Runbook markdown, agent YAML, `corpora.yaml` |
| **Ingest (batch)** | Platform Jobs: chunk → embed → write Azure index / FAISS / Delta→VS |
| **Retrieval** | `RetrievalProvider` at API runtime |
| **Data plane** | LangGraph + SQL + Foundry (RCA still telemetry-first) |
| **Control plane** | StateStore — **not** the vector index |
| **Observability** | LangSmith traces for retrieve + LLM steps |

Vector indexes are **not** StateStore. Keep catalog/session/audit separate from embeddings.

---

## 4. Plug-and-play backends

| Backend | `EDIM_RETRIEVAL` | Typical use |
|---------|------------------|-------------|
| **none** | `none` (default) | Retrieval disabled; RCA still works |
| **memory** | `memory` | Unit tests / ephemeral demos |
| **faiss** | `faiss` | Local laptop **or** Databricks Volume path |
| **azure_ai_search** | `azure_ai_search` | **Deployed default** (DEV/PROD) |
| **databricks_vector** | `databricks_vector` | Per-corpus override when index is UC-native |

```bash
# Local
pip install 'edim-dde-ai[faiss]'
export EDIM_RETRIEVAL=faiss
export EDIM_FAISS_INDEX_PATH=/tmp/edim-indexes
# or Volume:
# export EDIM_FAISS_INDEX_PATH=/Volumes/catalog/schema/edim_indexes

# Deployed
pip install 'edim-dde-ai[azure-search]'
export EDIM_RETRIEVAL=azure_ai_search
export EDIM_AZURE_SEARCH_ENDPOINT=https://<service>.search.windows.net
export EDIM_AZURE_SEARCH_KEY=...          # Key Vault in PROD
export EDIM_AZURE_SEARCH_INDEX=spark-runbooks
# optional corpus→index map:
# export EDIM_AZURE_SEARCH_CORPUS_MAP=spark-runbooks:spark-runbooks
```

Extras: `[faiss]`, `[azure-search]`, `[databricks-vector]`, or `[retrieval]` for all.

---

## 5. Code layout

| Package | Role |
|---------|------|
| **`edim-dde-ai` `retrieval/`** | Protocol, memory/FAISS/Azure/Databricks, corpus registry, `rag.retrieve` node |
| **`edim-dde-domain`** | `config/corpora.yaml`, sample `knowledge/spark-runbooks/`, RCA query builder + prompt wiring |
| **`edim-dde-api`** | Lifespan `configure_retrieval_from_env()`, `/health.retrieval`, curated ingest API |

`/health` example:

```json
{
  "status": "ok",
  "observability": "langsmith",
  "state_store": "postgres",
  "retrieval": "faiss"
}
```

---

## 6. `spark_rca` pilot flow (detailed)

```text
SQL collectors → assemble_evidence → rule_classify
  → build_retrieval_query          (domain.rca.*)
  → rag.retrieve                   (framework; corpus=spark-runbooks)
  → prepare_llm_payload            (injects runbook_context)
  → llm_chain (rca)                (Foundry)
  → parse / validate
```

1. Telemetry evidence is still authoritative (Unity Catalog / SQL).
2. Classification + failure text become `retrieval_query`.
3. `rag.retrieve` calls the active provider (or per-corpus override).
4. Hits are formatted into `runbook_context` and added to the human prompt.
5. The LLM may align actions with runbooks but must ground facts in `evidence_pack`.

If `EDIM_RETRIEVAL=none` or the index is empty, RCA continues; the prompt shows that no hits were retrieved.

---

## 7. YAML contract

Agent-level policy (validated when present):

```yaml
rag:
  enabled: true
  corpus: spark-runbooks
  top_k: 5
  search_mode: hybrid
  cite: true
```

Graph node (actual execution):

```yaml
- id: retrieve_runbooks
  type: rag.retrieve
  corpus: spark-runbooks
  top_k: 5
  search_mode: hybrid
  query_key: retrieval_query
  output_key: runbook_hits
  context_key: runbook_context
```

Corpus registry (`edim-dde-domain/.../config/corpora.yaml`) maps logical names to Azure index names / optional provider overrides.

---

## 8. FAISS local + Databricks Volume

FAISS stores `{corpus}.faiss` + `{corpus}.meta.json` under `EDIM_FAISS_INDEX_PATH`.

```bash
# Build index from packaged sample runbooks
python - <<'PY'
from pathlib import Path
from edim_dde_ai.retrieval.faiss_provider import build_faiss_index_from_dir
import edim_dde_domain

root = Path(edim_dde_domain.__file__).resolve().parent / "knowledge" / "spark-runbooks"
n = build_faiss_index_from_dir(
    corpus="spark-runbooks",
    source_dir=root,
    index_dir="/tmp/edim-indexes",  # or /Volumes/.../edim_indexes
)
print("indexed", n)
PY
```

Same code path for Volumes — the runtime must be able to read/write that path.

Embeddings for FAISS default to a deterministic **hashing embedder** (no cloud dependency). Platform Jobs may later swap to Foundry/Azure embeddings for production quality.

---

## 9. Ingest: Jobs vs API

### Platform Jobs (primary)

1. Read approved sources (Git, SharePoint export, Delta, etc.).
2. Chunk + embed (Azure / Databricks pipeline).
3. Write to Azure AI Search index **or** rebuild FAISS on a Volume **or** sync Databricks Vector Search.

### Curated API (Acceptance + summary)

```bash
curl -s -X POST localhost:8080/api/v1/knowledge/ingest \
  -H 'Content-Type: application/json' \
  -d '{
    "corpus": "spark-runbooks",
    "doc_id": "oom-v2",
    "summary": "Executor OOM playbook",
    "text": "Full markdown body...",
    "accepted": true,
    "source": "ops-review"
  }'
```

- `accepted` **must** be `true` (HTTP 400 otherwise).
- `summary` is prepended to `text` to improve retrieval.
- Works for **FAISS / memory / Azure** upserts; Databricks VS returns **501** (Jobs-owned).

---

## 10. Programmatic API

```python
from edim_dde_ai.retrieval import (
    configure_retrieval_from_env,
    search_corpus,
    set_retrieval_provider,
    MemoryRetrieval,
)

configure_retrieval_from_env()
hits = search_corpus("OutOfMemoryError executor", corpus="spark-runbooks", top_k=5)
```

Custom backends: implement `RetrievalProvider` and call `set_retrieval_provider(...)`.

---

## 11. Environment variables

| Variable | Purpose |
|----------|---------|
| `EDIM_RETRIEVAL` | `none` \| `memory` \| `faiss` \| `azure_ai_search` \| `databricks_vector` |
| `EDIM_FAISS_INDEX_PATH` | Directory for FAISS files (local or Volume) |
| `EDIM_FAISS_DIM` | Hash embed dim (default 384) |
| `EDIM_AZURE_SEARCH_ENDPOINT` | Azure AI Search endpoint |
| `EDIM_AZURE_SEARCH_KEY` | Query/admin key |
| `EDIM_AZURE_SEARCH_INDEX` | Default index name |
| `EDIM_AZURE_SEARCH_CORPUS_MAP` | `corpus:index,...` overrides |
| `EDIM_DBX_VS_ENDPOINT` | Databricks Vector Search endpoint |
| `EDIM_DBX_VS_INDEX` | Default VS index |
| `EDIM_DBX_VS_CORPUS_MAP` | `corpus:index,...` overrides |

Also listed in [Environment variables](../reference/env-vars.md).

---

## Related

- [Reference architecture](../architecture/reference-architecture.md)
- [YAML schema](../framework/yaml-schema.md)
- [State store](state-store.md) (control plane — different from indexes)
- [Observability](observability.md)
- Roadmap items **BL-021–024**
