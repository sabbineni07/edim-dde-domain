# LangSmith setup guide (SDBX / DEV / PROD)

You asked for help getting productive with LangSmith. This guide is written for that — from zero to first traced EDIM agent run.

**Phase 0:** enable tracing + projects per environment.  
**Later (Phase 2+):** datasets, evaluators, CI quality gates.

---

## 1. What LangSmith is (30 seconds)

[LangSmith](https://smith.langchain.com/) is LangChain’s product for:

- **Tracing** — see each agent/LLM/tool span, latency, tokens, errors
- **Debugging** — open a failed run and inspect inputs/outputs
- **Evaluation** (later) — golden datasets and scorers

EDIM uses **LangGraph** + **langchain-core**, so tracing turns on primarily via **environment variables**. The runtime also attaches **tags** (`agent_id`, `EDIM_ENV`, `request_id`).

LangSmith is the **recommended** backend. The framework also supports selecting **MLflow** or **none** via `EDIM_OBSERVABILITY` — see [observability providers](observability.md).

---

## 2. Can we run LangSmith locally in Docker?

**Short answer:** not as a free/open-source local stack. Self-hosted LangSmith **does** ship Docker Compose for development/testing, but it is an **Enterprise add-on** and requires a **license key** from LangChain.

| Option | Local laptop? | License | Recommendation for EDIM |
|--------|---------------|---------|-------------------------|
| **LangSmith Cloud (SaaS)** | Yes — app runs locally, traces go to cloud | Free/team/enterprise tiers | **Use this for local testing** |
| **Self-hosted LangSmith (Docker Compose)** | Yes | **Enterprise license required** | Only if FinTech/data-residency mandates it and you have a key |
| **Self-hosted on Kubernetes** | No (cluster) | Enterprise | PROD-style private deployment later |
| **No LangSmith UI locally** | N/A | — | You can still run agents; you just won’t get the LangSmith UI |

### Recommended path for local testing (no Enterprise license)

1. Keep the EDIM API on your laptop (`uvicorn`).
2. Point tracing at **LangSmith Cloud** with a personal/team API key.
3. Use project `edim-dde-sdbx` (or `edim-dde-dev`) so local noise stays out of PROD.

```bash
export EDIM_ENV=sdbx
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=lsv2_pt_...          # from https://smith.langchain.com
export LANGCHAIN_PROJECT=edim-dde-sdbx
export LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

Your agent code stays local; only **redacted telemetry** (traces) leaves the machine.

### Self-hosted Docker (only with Enterprise license)

Official docs: [Self-host LangSmith](https://docs.langchain.com/langsmith/self-hosted) (Docker Compose is documented for local/dev testing; production uses Kubernetes).

Typical shape (illustrative — follow current LangChain docs + your license packet):

```bash
# Requires LANGSMITH_LICENSE_KEY from LangChain sales/support
# Compose brings up LangSmith UI + Postgres + Redis + ClickHouse, etc.
# Intended for local/dev testing of self-host — not production.
docker compose up
```

Then point EDIM at your local endpoint instead of SaaS:

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=<key-from-your-self-hosted-instance>
export LANGCHAIN_ENDPOINT=http://localhost:<port>   # per compose docs
export LANGCHAIN_PROJECT=edim-dde-sdbx
```

**Do not** attempt unlicensed Docker images — they fail with invalid/missing license errors.

### FinTech note

If your security team forbids sending traces to SaaS, escalate for an **Enterprise self-hosted** evaluation. Until then, either:

- use SaaS with PII redaction + non-prod projects only, or  
- run agents **without** tracing (`EDIM_LANGSMITH_ENABLED=false` / unset `LANGCHAIN_TRACING_V2`).

---

## 3. Create projects (one per env)

1. Sign in at https://smith.langchain.com/
2. Open **Settings → API Keys** → create a key (store in Key Vault for DEV/PROD)
3. Create three **projects** (names are conventions — match your org if different):

| Environment | Suggested project name |
|-------------|------------------------|
| SDBX | `edim-dde-sdbx` |
| DEV | `edim-dde-dev` |
| PROD | `edim-dde-prod` |

Use a **different API key** for PROD if your org requires separation.

---

## 4. Environment variables

```bash
# Turn on LangChain/LangGraph tracing to LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...          # from LangSmith settings
LANGCHAIN_PROJECT=edim-dde-dev         # must match the env you are in
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# EDIM correlation
EDIM_ENV=dev
```

For PROD, load `LANGCHAIN_API_KEY` from Key Vault (secret name `langchain-api-key` by default). See [security-baseline.md](security-baseline.md).

Optional: `EDIM_LANGSMITH_ENABLED=false` forces tracing off even if LangChain env is set.

---

## 5. Install

Tracing works with `langchain-core` / `langgraph` already in `edim-dde-ai`. For the LangSmith client extras:

```bash
pip install 'edim-dde-ai[observability]'
# or
pip install langsmith
```

---

## 6. Run an agent and find the trace

```bash
# from repo with .env loaded for DEV
uvicorn edim_dde_api.main:app --port 8080

curl -s localhost:8080/api/v1/recommendations \
  -H 'content-type: application/json' \
  -H 'x-request-id: demo-001' \
  -d '{"job_id":"<id>","cluster_id":"<id>","include_explanation":false}'
```

Then in LangSmith UI:

1. Open project `edim-dde-dev`
2. Filter by tag `agent_id:cluster_tuning` or metadata `request_id=demo-001`
3. Open the run → inspect spans (SQL nodes won’t all appear as LLM children; LLM spans show under `llm_chain`)

---

## 7. What to look for (new-user checklist)

| Question | Where in LangSmith |
|----------|--------------------|
| Did the run fail? | Run list status / error |
| Which model / deployment? | LLM run metadata |
| How many tokens? | LLM run metrics |
| What prompt was sent? | LLM run inputs (after PII redaction) |
| Correlate to an API call? | Metadata `request_id`, tag `env:dev` |

---

## 8. PII and FinTech caution

Traces may include prompt text. EDIM applies **basic PII redaction** (SSN, PAN, account, member id) before attaching string metadata. Still avoid putting secrets in prompts. See [pii-guardrails.md](pii-guardrails.md).

---

## 9. Troubleshooting

| Symptom | Fix |
|---------|-----|
| No runs appear | `LANGCHAIN_TRACING_V2=true`? Correct `LANGCHAIN_API_KEY`? Correct `LANGCHAIN_PROJECT`? |
| Runs in wrong project | `LANGCHAIN_PROJECT` must match env |
| 401 from LangSmith | Rotate API key; check Key Vault secret |
| Local works, Apps doesn’t | Ensure Apps process has env / Key Vault mapping; outbound HTTPS allowed |
| Too much noise in SDBX | Keep SDBX project separate; don’t point DEV app at `edim-dde-sdbx` |
| Docker “license key is not valid” | Self-host requires Enterprise license — use SaaS for local testing instead |

---

## 10. Next (not Phase 0)

- Upload golden datasets for `cluster_tuning` / `spark_rca`
- Add evaluators and CI gates (backlog BL-033–035)
- Dashboard / alerts (BL-030)

---

## Related

- [Environments](environments.md)
- [Config → observability flow](../architecture/config-to-observability.md)
- [Reference architecture](../architecture/reference-architecture.md)
