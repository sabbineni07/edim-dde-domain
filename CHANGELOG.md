# Changelog — edim-dde-domain

## 1.0.0 — 2026-07-31 (Release 1 / Phase 0)

### Added
- Azure Key Vault secret bootstrap (`security.keyvault`)
- Expandable PII redaction patterns (`security.pii`) — SSN, credit card, account number, member id
- Optional extra `[keyvault]`
- Phase 0 engineer docs: reference architecture + PPT deck, environments, security, PII, LangSmith setup, **pluggable observability**, **control-plane state store**, **retrieval & RAG** (`spark_rca` runbook pilot), YAML schema, orchestration topology
- Sample knowledge corpus: `knowledge/spark-runbooks/` + `config/corpora.yaml`

### Notes
- Package version aligned to R1 `1.0.0` with `edim-dde-ai` and `edim-dde-api`. Publishing to an internal index is deferred to ops.
- Primary engineer guides: `docs/platform/state-store.md`, `docs/platform/retrieval-and-rag.md`.