# Configuration

**Learning path:** G1 · [Preface](../README.md)  
**← Previous:** [External plugins](../build-agents/external-plugins.md) · **Next:** [HTTP endpoints](endpoints.md) →

## Chapter summary

Runtime configuration for the API host: minimum local env for live SQL + Foundry, observability toggles, and pointers to the full env catalog and deploy guides.

**Outcome:** you can bring up a laptop process that reaches Databricks and Foundry safely.

---

See also [environment variables](../reference/env-vars.md).

## Minimum local (live SQL + Foundry)

```bash
az login

export DATABRICKS_HOST=adb-….azuredatabricks.net
export DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<id>
export DATABRICKS_JOB_CLUSTER_METRICS_TABLE=catalog.schema.job_cluster_metrics
export DATABRICKS_SPARK_METRICS_TABLE=catalog.schema.spark_metrics
export DATABRICKS_SPARK_LOGS_TABLE=catalog.schema.spark_logs

export AZURE_OPENAI_ENDPOINT=https://….openai.azure.com
export AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

Template: `edim-dde-domain/.env.example`.

## Corporate network quick profile (optional)

Use this profile when your laptop is behind a corporate package mirror and outbound proxy.

```bash
# Install-time (pip)
export PIP_INDEX_URL='https://prod.artifactory.nfcu.net/artifactory/api/pypi/pypi/simple'
export PIP_TRUSTED_HOST='prod.artifactory.nfcu.net'

# Runtime (only when required by your network)
export HTTP_PROXY='http://binnacle.nfcu.net:8080'
export HTTPS_PROXY='http://binnacle.nfcu.net:8080'
export NO_PROXY='127.0.0.1,localhost'
```

Observed during live smoke: runtime proxy paths can return `407 Proxy Authentication Required` for Databricks/Azure SDK token-exchange calls unless proxy auth is fully configured for Python runtime traffic. If this occurs, run smoke from a shell without proxy vars (or use your network-approved direct route).

```bash
unset HTTP_PROXY HTTPS_PROXY
```

If using Key Vault bootstrap, keep `EDIM_KV_SECRET_MAP` in `ENV_VAR_NAME:vaultSecretName` order.
Example:

```text
EDIM_KV_SECRET_MAP=EDIM_FOUNDRY_CLIENT_ID:DLABS-DIM-ADB-APP-AIF-APPID,EDIM_FOUNDRY_CLIENT_SECRET:DLABS-DIM-ADB-APP-AIF-APPKEY
```

Do not reverse the pair order.

## API-specific

```bash
# Browser CORS allow-list (empty = no cross-origin)
export EDIM_CORS_ORIGINS=http://localhost:4200

# External agent plugin roots
export EDIM_AGENT_DIRS=/opt/edim-agents/acme

# Control plane (StateStore) — agent catalog, sessions, audit
# Local: docker compose -f docker-compose.state-store.yml up -d
export EDIM_STATE_STORE=postgres
export EDIM_DATABASE_URL=postgresql://edim:edim@localhost:5432/edim
# Deployed: EDIM_STATE_STORE=cosmos + EDIM_COSMOS_* (see state-store.md)

# Product history (RecommendationStore) — tuning/RCA rows + lifecycle status
# Default: inherits EDIM_STATE_STORE. Set explicitly only to diverge or disable.
# export EDIM_RECOMMENDATION_STORE=none      # HTTP still works; no history ids
# export EDIM_RECOMMENDATION_STORE=cosmos    # same account as StateStore is typical
#
# Example StateStore document:  { "agent_id": "cluster_tuning", "lifecycle": "approved" }
# Example RecommendationStore: { "recommendation_id": "…", "job_id": "123", "status": "proposed", "response": {…} }
# Full guides: platform/state-store.md · platform/recommendation-store.md
```

## Run

```bash
cd edim-dde-api
uvicorn edim_dde_api.main:app --reload --port 8080
curl -s localhost:8080/health   # includes observability + state_store + recommendation_store
```

Full store guides: [Control-plane state store](../platform/state-store.md) · [Recommendation store](../platform/recommendation-store.md).

## Observability (LangSmith)

`uvicorn` does **not** load `edim-dde-domain/.env` automatically — export vars in the shell that starts the API (or use `make host-run`).

```bash
export EDIM_OBSERVABILITY=langsmith
export EDIM_ENV=dev
export LANGCHAIN_TRACING_V2=true          # required for LangGraph tracing (not LANGSMITH_TRACING alone)
export LANGCHAIN_API_KEY=lsv2_pt_...
export LANGCHAIN_PROJECT=edim-dde-dev     # tracing project in LangSmith UI — not EDIM_ENV
# Self-hosted:
# export LANGCHAIN_ENDPOINT=https://your-host.example.net/api/v1
```

Validate: `GET /health` → `"observability": "langsmith"`; dry agent call with `X-Request-Id`; find run in LangSmith under **My First App** → project **`LANGCHAIN_PROJECT`**.

Full guide (UI hierarchy, `LANGCHAIN_*` vs `LANGSMITH_*`, Windows steps, troubleshooting): [LangSmith setup](../platform/langsmith-setup.md).

**Smoke testing (dry Foundry-only or live SQL):** [Live & dry smoke test](../contribute/live-smoke-test.md).

**Deploy (Databricks Apps / Docker / ACA):** [Deploy & hosting](deploy-and-hosting.md).

## Summary

- Prefer env catalog + LangSmith setup for full key lists.
- Validate with `/health` and a dry agent call before deploy.

**Next →** [HTTP endpoints (G2)](endpoints.md)

<!-- edim-learning-nav -->
---

← [External plugins](../build-agents/external-plugins.md) · [Preface](../README.md) · [HTTP endpoints](endpoints.md) →
