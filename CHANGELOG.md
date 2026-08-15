# Changelog — edim-dde-domain

## Unreleased

### Added
- Cluster tuning **guardrail retry**: one re-prompt when retryable clamps remain (`sizing_needs_retry`); max 2 sizing LLM calls; state exposes `sizing_attempts` / `guardrail_retries`
- Cluster tuning **`validate_performance`** graph node (rule-based peak fitness) → `performance_validation` on agent state / API
- Engineer guide: **recommendation lifecycle store** (`docs/platform/recommendation-store.md`) + endpoints / env-var updates
- Cluster tuning **historical context**: `rag.retrieve` on corpus `cluster-tuning-guidance` + RecommendationStore history → `{historical_context}` (sample knowledge under `knowledge/cluster-tuning-guidance/`)
- **Experience index (feature-first history):** `ClusterTuningExperienceTransform` → corpus `cluster-tuning-outcomes`; auto-index on recommendation save/status; `compose_historical_context` prefers experience similarity search; heuristic peers = cold-start fallback; guide §6c
- **Cluster-tuning quality hardening:** evidence-precedence/history-aware prompts,
  YAML-configured resource-pressure + historical-context skills, principle-focused
  guidance corpus, removal of fixed over/under/OOM index vocabulary,
  history-aware explanations, and `cluster_tuning.quality` deterministic evaluator
  with config-driven directional gates
- Engineer guide: **§6b deep-dive** in `docs/platform/retrieval-and-rag.md` — store ranking (two-shelf `select_history_records`, `similarity_score` weights/scales table + SKU-family gotcha), index-build internals (hashing embedder, one-vector-per-file, `.faiss`/`.meta.json`), and the heuristic-vs-embeddings design choice; fixed the FAISS index snippet arg (`source_dir`) and the stale `historical_context` row in `docs/domain/cluster-tuning-agent.md`
- Engineer guide: **node-local config abstraction** — `docs/framework/nodes-and-routers.md` §5–6 (config opaque to framework; build-time closure → state hand-off; non-graph-consumer bootstrap load) and the `resource_pressure` YAML/state single-source-of-truth block in `docs/domain/cluster-tuning-agent.md` Step C/D
- Engineer guide: **collapsible in-depth pressure deep-dive** in `docs/domain/cluster-tuning-agent.md` — design rationale (pressure axes vs named scenarios; pressure ≠ failure; role separation), full `resource_pressure` parameter reference, "add a disk/spill dimension" recipe, the honest no-code-changes boundary, and `history_*` knob reference

## 1.0.0 — 2026-07-31 (Release 1)

### Added
- Azure Key Vault secret bootstrap (`security.keyvault`)
- Expandable PII redaction patterns (`security.pii`) — SSN, credit card, account number, member id
- Optional extra `[keyvault]`
- R1 engineer docs: reference architecture + PPT deck, environments, security, PII, LangSmith setup, **pluggable observability**, **control-plane state store**, **retrieval & RAG** (`spark_rca` runbook pilot), YAML schema, orchestration topology
- Sample knowledge corpus: `knowledge/spark-runbooks/` + `config/corpora.yaml`

### Notes
- Package version aligned to R1 `1.0.0` with `edim-dde-ai` and `edim-dde-api`. Publishing to an internal index is deferred to ops.
- Primary engineer guides: `docs/platform/state-store.md`, `docs/platform/retrieval-and-rag.md`.