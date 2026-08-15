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
│   Pilots: spark_rca runbooks · cluster_tuning guidance + experience      │
│           outcomes + store history                                       │
└──────────────────────────────────────────────────────────────────────────┘
```

| Term | Meaning |
|------|---------|
| **Similarity search** | Find nearest / best-matching chunks (vector and/or keyword) |
| **Hybrid search** | Combine vector + keyword signals (`search_mode: hybrid`) |
| **RAG** | Application pattern that **uses** retrieval, then an LLM |
| **Corpus** | Logical knowledge set (e.g. `spark-runbooks`, `cluster-tuning-outcomes`) — not a backend name |
| **Experience index** | Derived situation/action cards from RecommendationStore writes, searched by **features** (see §6c) |

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
  → prepare_sizing_payload   (merges experience hits + store job shelf + guidance
                              into historical_context)
  → llm_chain (sizing) → guardrails → …
```

`historical_context` is built from **three independent lanes** that only meet in one prompt string. Different storage, different code, different failure modes; **any can be empty** and sizing still runs.

| Lane | Source | What it is | Populated by |
|------|--------|------------|--------------|
| **A — written guidance** | `rag.retrieve` → corpus `cluster-tuning-guidance` | Human-authored playbooks | You pre-build an index (§6b.2) |
| **B′ — past experiences (primary)** | Similarity search → corpus `cluster-tuning-outcomes` | Situation/action cards derived from past recommendations (**feature** similarity, not `job_id`) | Automatic index on RecommendationStore write (§6c) |
| **B — this job's store rows** | `RecommendationStore` | Thin **same-`job_id`** shelf; heuristic peer ranking only as **cold-start fallback** when B′ is empty | `/recommend` persist + PATCH status |

All are **secondary** to live metrics / sizing hints. Empty store + `EDIM_RETRIEVAL=none` → `historical_context: "None"`. The merge (`compose_historical_context`) appends whichever blocks exist (experience → store → guidance), keeps them visually separate, and truncates at **6000 chars**. Failures degrade to *no history*, never a failed request. On a guardrail **retry** the graph reuses `historical_context` already on state.

**Tuning vs chat (same data, different intent):**

| Intent | Path |
|--------|------|
| **Sizing / “jobs like this situation”** | Experience corpus (features) + optional same-job shelf |
| **“What happened to job X?”** | `RecommendationStore.list(job_id=X)` (entity path); `job_id` is also in experience **metadata** for filtered search later |

YAML knobs on `prepare_sizing_payload`:

```yaml
- id: prepare_sizing_payload
  type: domain.tuning.prepare_sizing_payload
  history_job_top_n: 5
  history_similar_top_n: 5           # heuristic Shelf 2; used only when experience index is empty
  history_candidate_limit: 80
  history_prefer_statuses: [applied, accepted, proposed]
  history_experience_top_k: 5
  history_experience_corpus: cluster-tuning-outcomes
  history_heuristic_fallback: true   # false → never use heuristic peer ranking
```

### 6b.1 Lane B — store shelves (`select_history_records`)

- **Shelf 1 — this job's own past.** Exact `job_id` match; newest-first within `history_prefer_statuses`. Cap `history_job_top_n`. Always available for the entity/chat story.
- **Shelf 2 — heuristic peers (fallback only).** `similarity_score()` arithmetic (SKU / util / tokens / status). Used **only when** the experience index returned no hits (or `history_heuristic_fallback: false` disables it entirely). When experience hits exist, Shelf 2 is skipped so the prompt is not flooded with duplicate peer content.

`similarity_score()` terms (fallback path; max ≈ **7.9**):

| Term | Rule | Points |
|------|------|--------|
| SKU match | exact `azure_worker_vm_size` | **3.0** |
| SKU “family” | first segment after `standard_` (really a *size* token — `d8s` ≠ `d16s`) | **1.0** |
| `max_worker_nodes_provisioned` | linear falloff, weight 1.5, scale 16 | 0–1.5 |
| peak CPU / mem % | weight 1.0, scale 50 each | 0–1.0 each |
| avg / p99 workers | weight 1.0, scale 8 each | 0–1.0 each |
| token overlap | `0.5 × Jaccard` | 0–0.5 |
| status bonus | `max(0, 0.4 − 0.1 × rank)` | 0–0.4 |

### 6b.2 Lane A — building the guidance index

Sample docs: `edim_dde_domain/knowledge/cluster-tuning-guidance/`. Mechanics of local FAISS + `HashingEmbedder`:

- **One file = one vector. No chunking.** Prefer short, single-topic files.
- **Text → 384 numbers** via token hashing (`sha256` → slot + sign); vocabulary overlap, not meaning.
- Disk: `{corpus}.faiss` + `{corpus}.meta.json` under `EDIM_FAISS_INDEX_PATH` (row *N* ↔ vector *N*).
- Query: `build_retrieval_query` → embed → `k = min(top_k, ntotal)` → optional hybrid `+0.05` keyword boost.
- **`search_corpus` de-dupes** by `id` then by `action_signature` / content hash so duplicate guidance does not enter the prompt.

```python
from pathlib import Path
import edim_dde_domain
from edim_dde_ai.retrieval.faiss_provider import build_faiss_index_from_dir

root = Path(edim_dde_domain.__file__).resolve().parent / "knowledge" / "cluster-tuning-guidance"
build_faiss_index_from_dir(corpus="cluster-tuning-guidance", source_dir=root)
```

Requires `EDIM_RETRIEVAL=faiss` and `EDIM_FAISS_INDEX_PATH`. Deployed: corpus → Azure index via `config/corpora.yaml`.

### 6b.3 Design evolution — heuristic → experience index

| Option | Role now |
|--------|----------|
| **A — heuristic Shelf 2** | **Cold-start fallback** when `EDIM_RETRIEVAL=none` or the outcomes corpus is empty |
| **B — experience index** | **Primary** cross-job learning (see §6c) |
| **C — SQL-side similarity** | Still rejected — breaks plug-and-play stores |

---

## 6c. Experience index (platform — all future agents)

Cross-job learning must **not** key primarily on `job_id`. Many jobs share almost the same cluster shape and different jobs share the same failure mode (over-provisioned / under-provisioned / OOM). The **experience index** is the platform answer.

```text
RecommendationStore.save / update_status
        │  ExperienceIndexingStore proxy (automatic)
        ▼
ExperienceTransform(agent_id)   ← domain “index parser”
        │
        ▼
ExperienceDocument (situation + action text + metadata)
        │  upsert doc_id = recommendation_id
        ▼
RetrievalProvider corpus (e.g. cluster-tuning-outcomes)
        │
        ▼
search_corpus(query from live features) → de-duped hits → sizing prompt
```

### Layers (do not collapse)

| Layer | Role |
|-------|------|
| **RecommendationStore** | System of record — lifecycle, PATCH, exact job history |
| **ExperienceDocument** | Derived card — situation labels + action text for similarity |
| **RetrievalProvider** | Same FAISS / Azure / Databricks backends as runbooks |

### Index parser (`ExperienceTransform`)

Domain packs register one transform per `agent_id` at bootstrap (`register_experience_transform`). Platform code never hard-codes tuning field names.

For `cluster_tuning` (`helpers/experience_transform.py`):

1. Read metrics + reason codes + recommendation payload from the record.
2. Infer **situation labels**, e.g. `over_provisioned`, `under_provisioned`, `oom_or_memory_pressure`, `sku_change`, `moved_to_memory_sku`. `over_provisioned` and `under_provisioned` are **mutually exclusive** (live utilization wins when reason codes conflict), and reason codes that describe the *proposed change* — notably `PERFORMANCE_DEGRADATION_RISK` — must not be read as observed cluster state.
3. Build **action lines**, e.g. `reduced max_workers 16 → 8`, `changed sku D8s → D4s`.
4. Emit index text:

```text
Situation: over_provisioned, sku_change
Signals: sku=… max_workers=… peak_cpu_pct=… …
Reason codes: …
Action: reduced max_workers …; changed sku …
Outcome: applied
```

5. Put `job_id` / `cluster_id` / `recommendation_id` / `status` in **metadata** (entity filters for chat), not as the retrieval key.

### When documents are written / removed

| Status | Experience index |
|--------|------------------|
| `proposed`, `accepted`, `applied` | **Upsert** (idempotent by `recommendation_id`) |
| `rejected`, `superseded` | **Delete** from the corpus |

`proposed` is indexed so local demos work before anyone PATCHes accepted/applied; metadata `status` remains available for future boosts.

Wiring: `set_recommendation_store` wraps backends in `ExperienceIndexingStore` so every `save` / `update_status` updates the index. Failures log and never fail the HTTP path. No-op when `EDIM_RETRIEVAL=none` or no transform is registered.

### De-duplication

| Problem | Fix |
|---------|-----|
| Same recommendation indexed twice | Upsert by `recommendation_id` (verified: 2× re-save → 1 doc) |
| Same *action* from many jobs in top-k | `search_corpus(..., dedupe=True)` keeps highest score per `id`, then per `action_signature` / content hash |
| Same markdown path re-indexed | Path-based `doc_id` on guidance corpora |

**Duplicates are counted, not discarded.** Many jobs hitting the same situation is *signal*, so the surviving hit carries `metadata['occurrences']` and `metadata['also_job_ids']`, rendered in the prompt as `occurrences=3 also_jobs=['job-1001', …]`. The model sees "this action was applied 3 times across jobs" once, instead of three identical paragraphs — or, worse, silently losing that it is a common pattern.

### Adding a future agent

1. Implement `ExperienceTransform` for that `agent_id` + corpus name.
2. Register at bootstrap; add corpus to `config/corpora.yaml`.
3. Build the agent query from **features**, not ids; keep store list-by-id for chat.

### Chat vs tuning (recommendation)

```text
Tuning prompt sections:
  [Similar past experiences]   ← feature search (little job_id noise)
  [Prior recommendations]      ← same job_id only (when present)
  [Retrieved sizing guidance]  ← playbooks

Chat / “explain job X”:
  RecommendationStore.list(job_id=X)   ← entity path
  optional: search outcomes with filter metadata.job_id=X
```

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
