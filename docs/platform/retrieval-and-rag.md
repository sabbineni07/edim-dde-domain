# Retrieval, similarity search, and RAG (C7)

**Learning path:** C7 · [Guide home](../README.md)  
**← Previous:** [Recommendation store](recommendation-store.md) · **Next:** [YAML schema](../framework/yaml-schema.md) →

This guide explains **similarity search vs RAG**, the pluggable **`RetrievalProvider`** backends (FAISS · Azure AI Search · Databricks Vector Search), how **`spark_rca`** uses runbook grounding, design patterns, and how engineers operate local vs deployed indexes.

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
│   Pilots: spark_rca runbooks · cluster_tuning guidance + store history   │
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

## 1b. Design patterns (GoF)

| Pattern | Where | Example |
|---------|-------|---------|
| **Strategy** | `RetrievalProvider` implementations | Swap FAISS ↔ Azure via `EDIM_RETRIEVAL` |
| **Protocol** | `retrieval/protocols.py` | `search` / `upsert` / `delete` / `ping` |
| **Registry** | process-wide provider + `corpora.yaml` | `provider_for_corpus("spark-runbooks")` |
| **Facade** | `search_corpus()`, `rag.retrieve` node | Agents never import Azure SDK |
| **Builder** (ingest) | Jobs / `build_faiss_index_from_dir` | Assemble index from markdown tree |

```python
from edim_dde_ai import configure_retrieval_from_env
from edim_dde_ai.retrieval import search_corpus

configure_retrieval_from_env()  # Strategy from EDIM_RETRIEVAL
hits = search_corpus("OutOfMemoryError executor", corpus="spark-runbooks", top_k=5)
```

---

## 2. Decisions locked for EDIM

| Decision | Choice |
|----------|--------|
| Deployed default | **Azure AI Search** (`EDIM_RETRIEVAL=azure_ai_search`) |
| Local / Volume | **FAISS** file index under `EDIM_FAISS_INDEX_PATH` (local **or** Databricks Volume) |
| Per-corpus override | Optional in `corpora.yaml` (e.g. Databricks VS for a lakehouse corpus) |
| First pilots | **`spark_rca`** runbooks · **`cluster_tuning`** guidance + recommendation history |
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
| **`edim-dde-domain`** | `config/corpora.yaml`, sample `knowledge/spark-runbooks/` + `knowledge/cluster-tuning-guidance/`, RCA + tuning query builders + prompt wiring |
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

## 6b. `cluster_tuning` historical context

```text
SQL / metrics → normalize → build_retrieval_query → rag.retrieve (cluster-tuning-guidance)
  → prepare_sizing_payload   (merges RecommendationStore rows + guidance_context
                              into historical_context)
  → llm_chain (sizing) → guardrails → …
```

`historical_context` is built from **two independent lanes** that only ever meet in a single prompt string. Different storage, different code, different failure modes; **either can be empty** and sizing still runs.

| Lane | Source | What it is | Populated by |
|------|--------|------------|--------------|
| **A — written guidance** | `rag.retrieve` → `RetrievalProvider` | Human-authored playbook chunks from corpus `cluster-tuning-guidance` | You pre-build an index (below) |
| **B — past decisions** | `RecommendationStore` | Prior proposals this system produced: **same `job_id` first**, then **similar peer jobs** | Automatically, as `/recommend` persists records |

Both are **secondary** to live metrics / sizing hints. Empty store + `EDIM_RETRIEVAL=none` → `historical_context: "None"` (sizing still runs). The merge (`compose_historical_context`) appends whichever blocks exist, keeps them visually separate so the model can tell a past decision from a guideline, and truncates at **6000 chars**. The store lookup is wrapped — a DB outage degrades to *no history*, never a failed request. On a guardrail **retry** the graph reuses the `historical_context` already on state, so neither lane is hit twice.

YAML knobs on `prepare_sizing_payload`:

```yaml
- id: prepare_sizing_payload
  type: domain.tuning.prepare_sizing_payload
  history_job_top_n: 5          # max same-job rows (Shelf 1)
  history_similar_top_n: 5      # max similar other-job rows (Shelf 2); 0 disables Shelf 2
  history_candidate_limit: 80   # how many recent store rows to pull before ranking
  history_prefer_statuses: [applied, accepted, proposed]
```

### 6b.1 Lane B — how store rows are ranked (`select_history_records`)

Before sizing, the store holds rows from **every** job, not just this one. The selector pulls the `history_candidate_limit` most recent rows and fills **two shelves**:

- **Shelf 1 — this job's own past.** Rows whose `job_id` equals the incoming `job_id`. Ordered newest-first, then stable-sorted by `history_prefer_statuses` (so `applied`/`accepted` float up while newest stays first within each band). Capped at `history_job_top_n`. **No scoring** — an exact ID match never needs a heuristic.
- **Shelf 2 — jobs that look like this one.** Everything not already picked, scored by `similarity_score()` (below), sorted descending, capped at `history_similar_top_n`. Runs **even when Shelf 1 is full**, so peers still contribute. When Shelf 1 has anything, candidates scoring **< 0.25** are dropped as noise; when Shelf 1 is empty, that floor is not applied.

`similarity_score()` is plain arithmetic over four ideas — **no embeddings, no vector DB**. Max ≈ **7.9**.

| Term | Rule | Points |
|------|------|--------|
| SKU match | exact `azure_worker_vm_size` string | **3.0** |
| SKU family | else first segment after stripping `standard_` matches (e.g. `d8s`) | **1.0** |
| `max_worker_nodes_provisioned` | `weight × max(0, 1 − |Δ|/scale)`, weight 1.5, scale 16 | 0–1.5 |
| `peak_worker_cpu_utilization_pct` | same falloff, weight 1.0, scale 50 | 0–1.0 |
| `peak_worker_memory_utilization_pct` | weight 1.0, scale 50 | 0–1.0 |
| `avg_worker_nodes_consumed` | weight 1.0, scale 8 | 0–1.0 |
| `p99_worker_nodes_consumed` | weight 1.0, scale 8 | 0–1.0 |
| token overlap | `0.5 × Jaccard` of current metrics vs record's node type + reason codes + SKU | 0–0.5 |
| status bonus | `max(0, 0.4 − 0.1 × status_rank)` (`applied`=0 … `rejected`=4) | 0–0.4 |

Each numeric term is a **linear falloff**: identical values earn the full weight; a gap of one full *scale* earns **0** (clamped).

> **Gotcha — the "family" bonus is really a *size* bonus.** It compares only the first underscore segment, so `d8s` vs `d16s` do **not** match and earn **0**, even though both are D-series v5. Only an exact SKU string gets meaningful SKU credit. Consequence, with a `Standard_D8s_v5` / max 16 / CPU 28% / mem 41% incoming job (numbers from the real function):
>
> | Candidate | Score |
> |-----------|-------|
> | `Standard_D8s_v5`, applied, similar shape | **8.37** |
> | `Standard_E4ds_v5`, rejected, memory-bound | **2.68** |
> | `Standard_D16s_v5`, accepted, much bigger | **0.80** |
>
> A different instance family outranks the same family, purely because the bigger D16 job's node counts/CPU are >1 scale away and clamp to zero. If that ordering is wrong for the product, widen the scales or make the SKU compare family-aware — both are single-function changes in `helpers/historical_context.py`.

### 6b.2 Lane A — building the guidance index

Sample docs live in `edim_dde_domain/knowledge/cluster-tuning-guidance/`. "Building an index" converts each markdown file **once** into a numeric vector so the machine can answer *"which text is relevant to this cluster?"* instantly. The `.md` files stay the source of truth; the index is a **derived artifact** you can delete and rebuild.

Mechanics of the default local backend (`FaissRetrieval` + `HashingEmbedder`):

- **One file = one vector. No chunking.** The whole file is read as a single string, so a long multi-topic file becomes one blurry average — prefer several short, single-topic files.
- **Text → 384 numbers.** For each token: `sha256(token)`, first 4 bytes mod 384 pick a slot, byte 4 parity picks `+1`/`−1`; votes are summed and the vector is L2-normalized. Two docs are "close" when they **share vocabulary** — this is keyword matching, *not* meaning (`reduce max_workers` won't find `shrink the cluster`). Swap in Foundry / Azure OpenAI embeddings in the ingest job when you need real semantics.
- **What lands on disk** (under `EDIM_FAISS_INDEX_PATH`): `cluster-tuning-guidance.faiss` (the vectors, in insertion order, in a `IndexFlatIP`) and `cluster-tuning-guidance.meta.json` (per-doc `id` / full `text` / `metadata.path`). Row *N* in the sidecar is vector *N* in FAISS — that alignment is how a search hit becomes readable text.
- **Query time:** `build_retrieval_query` flattens live metrics into one line, it's embedded with the same embedder, FAISS returns `k = min(top_k, ntotal)` hits (so 2 indexed docs + `top_k: 4` → 2 hits), then hybrid mode adds `+0.05` per query word literally present and re-sorts.

Index it locally (run once; re-run when docs change):

```python
from pathlib import Path
import edim_dde_domain
from edim_dde_ai.retrieval.faiss_provider import build_faiss_index_from_dir

root = Path(edim_dde_domain.__file__).resolve().parent / "knowledge" / "cluster-tuning-guidance"
build_faiss_index_from_dir(corpus="cluster-tuning-guidance", source_dir=root)
```

Requires `EDIM_RETRIEVAL=faiss` **and** `EDIM_FAISS_INDEX_PATH=<dir>`. **Deployed** environments have no build step in the app: the corpus name maps to an Azure AI Search index via `config/corpora.yaml`, and an ingest job owns population.

### 6b.3 Design choice — why a heuristic for Lane B (not embeddings)

Three options were considered for ranking **store rows** (Lane B is structured records, distinct from Lane A's free text):

- **A — in-process heuristic (chosen).** `similarity_score()` over SKU/metric/token/status. Zero new infra, deterministic, debuggable, works the moment records exist, and needs no index rebuild. Cost: hand-tuned weights and the family gotcha above.
- **B — index recommendations into a `RetrievalProvider`.** Reuse FAISS/Azure to vector-search past records. More "semantic," but needs an ingest path per store, an index to keep in sync, and embeddings to earn their keep on what is mostly numeric data. A natural **later** layer if heuristic ranking proves insufficient.
- **C — SQL-side similarity.** Push scoring into Postgres/Cosmos. Fast at scale but backend-specific — breaks the plug-and-play `RecommendationStore` contract across memory/cosmos/redis.

A wins for R1 because it's backend-agnostic and immediately useful; B can slot in behind the same `select_history_records` seam without touching callers.

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

- [End-to-end design](../architecture/end-to-end-design.md)
- [Reference architecture](../architecture/reference-architecture.md)
- [YAML schema](../framework/yaml-schema.md)
- [State store](state-store.md) (control plane — different from indexes)
- [Observability](observability.md)
- Roadmap items **BL-021–024**

---

← [Recommendation store](recommendation-store.md) · [Guide home](../README.md) · [YAML schema](../framework/yaml-schema.md) →
