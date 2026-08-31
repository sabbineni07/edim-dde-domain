# Deployment targets and release runbook

**Learning path:** G3a · [Preface](../README.md)  
**← Previous:** [HTTP endpoints](endpoints.md) · **Next:** [Deploy & hosting](deploy-and-hosting.md) →

This page is the engineer-facing runbook for packaging and selecting an EDIM
runtime host. The agent definition, node implementations, and graph-building
rules are shared. Only the host adapter, process command, identity wiring, and
platform resources change.

!!! warning "Implementation status"
    ACA Native is the standard target and has a working local Docker baseline.
    The Standalone Agent Server adapter currently exposes the `cluster_tuning`
    pilot, but its `langgraph.json`, Agent Server runtime dependency, and ACA
    deployment bundle still need to be added. Full self-hosted LangSmith
    Deployment on AKS is an approved optional platform target, not an
    installation completed by this repository.

## 1. Choose a target

| Target | Use it for | Process/runtime | Ownership |
|---|---|---|---|
| **ACA Native** | Default production and non-production API hosting | `uvicorn edim_dde_api.main:app` | EDIM application/platform teams |
| **Standalone Agent Server on ACA** | A ready-made LangGraph runtime, threads, runs, and streaming | LangGraph Agent Server | EDIM application team plus ACA platform |
| **Full self-hosted LangSmith Deployment on AKS** | A complete private LangSmith control plane and Agent Server platform | LangSmith control plane + Agent Server | LangSmith/platform team |
| Databricks Apps | Data-local pilots or compatibility workloads | FastAPI | Databricks/application team |

Use **ACA Native** unless the agent specifically needs Agent Server APIs or the
organization has selected the full self-hosted LangSmith platform. Databricks
Apps remains supported, but it is not the standard EDIM runtime.

### 1.1 Selection rules

Choose ACA Native when:

- the API contract is the EDIM REST contract;
- Azure networking, managed identity, APIM, and Application Insights are the
  primary operating model;
- the agent can use the EDIM StateStore and queue/worker pattern for long work.

Choose Standalone Agent Server on ACA when:

- the consumer needs LangGraph threads, runs, streaming, or Agent Server
  lifecycle APIs;
- the team can operate PostgreSQL and Redis as external backing services;
- the team accepts that the LangSmith control plane is not included.

Choose Full self-hosted LangSmith Deployment on AKS when:

- the enterprise has approved the LangSmith license and platform ownership;
- the UI, control plane, Agent Server, and evaluation workflows must remain
  inside the Azure boundary;
- the team can operate the required Kubernetes workloads, data stores, secrets,
  upgrades, backups, and disaster recovery.

These are deployment targets, not three copies of the business logic. A single
versioned YAML agent package must remain deployable to each selected target.

## 2. Shared artifact and portability contract

### 2.1 Source layout

An agent release contains the YAML and code needed to construct the graph:

```text
edim-dde-domain/
  src/edim_dde_domain/agents/<agent_id>/
    <agent_id>.agent.yaml
    nodes.py
    logic.py
    content/
  src/edim_dde_domain/langsmith_entrypoint.py
edim-dde-ai/
  src/edim_dde_ai/graph/builder.py
edim-dde-api/
  src/edim_dde_api/main.py
  deploy/docker/
```

The YAML owns topology, node type IDs, routes, and non-secret configuration.
Python owns registered node implementations and platform integrations. Secrets,
tokens, hostnames that vary by environment, and user identity must come from
runtime configuration.

Graph construction must be deterministic and must not make network calls. SQL,
LLM, search, Key Vault, and telemetry calls happen when the graph is invoked,
using the selected runtime identity.

### 2.2 Two graph surfaces

The framework now provides two graph-building surfaces:

| Surface | State shape | Host |
|---|---|---|
| `build_graph(definition)` | Internal `AgentState` with a `data` channel | Existing FastAPI/ACA Native facade |
| `build_flat_graph(definition)` | Reducer-backed flat `dict[str, Any]` | Agent Server adapter and product-facing flat contracts |

`build_flat_graph()` uses a shallow merge reducer so nodes can return partial
updates without losing earlier request fields. Do not change the public state
shape in a host adapter without an API review.

The current Agent Server adapter is:

```python
from edim_dde_domain.langsmith_entrypoint import cluster_tuning_graph

graph = cluster_tuning_graph()
result = graph.invoke({"job_id": "...", "cluster_id": "...", "metrics": {...}})
```

It loads the same packaged YAML and node registrations used by the ACA Native
host. Adding an agent requires an explicit exported factory and a test; do not
let a request choose an arbitrary YAML file or Python import.

### 2.3 Agent Server manifest template

When the Agent Server dependency and deployment bundle are introduced, the
bundle should contain a manifest shaped like this:

```json
{
  "dependencies": ["."],
  "graphs": {
    "cluster_tuning": "./edim_dde_domain/langsmith_entrypoint.py:cluster_tuning_graph"
  },
  "env": ".env.example"
}
```

The exact manifest fields and CLI must match the approved LangGraph/LangSmith
version. Treat this as a template, not as an already-deployable file. Pin the
runtime version in the release and validate the import in CI.

## 3. Build a release

Run these steps from `edim-dde-api/` with the three repositories checked out as
siblings:

```bash
cd /path/to/edim/edim-dde-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"

pytest -q
make vendor-wheels
```

The generated release inputs are:

| Output | Used by |
|---|---|
| `deploy/databricks-app/vendor/*.whl` | Databricks Apps compatibility bundle |
| `deploy/databricks-app/requirements.vendor.txt` | Databricks Apps dependency install |
| `dist/*.whl` in each package | Private package index or image build |
| `deploy/docker/Dockerfile` | Production ACA Native image |
| `deploy/docker/Dockerfile.local` | Local reproducibility image |

`vendor/` is generated and gitignored. Rebuild it for every release unless the
organization has moved to a private package index. Never use editable
dependencies in a production image.

### 3.1 Package-data checks

Before publishing, confirm the domain wheel includes YAML and prompt content:

```bash
python -m build
python - <<'PY'
from pathlib import Path
from zipfile import ZipFile

wheel = sorted(Path("dist").glob("*.whl"))[-1]
with ZipFile(wheel) as archive:
    names = archive.namelist()
    assert any(name.endswith(".agent.yaml") for name in names)
print(wheel)
PY
```

Also verify:

- every YAML node and router type is registered;
- the selected graph factory imports in a clean environment;
- no `.env`, token, password, or private key is inside a wheel or image;
- the release version is recorded in all package changelogs.

## 4. Target A — ACA Native (standard)

ACA Native runs the existing FastAPI application as a normal container. The
image does not contain Azure credentials. ACA injects identity and environment
configuration at runtime.

### 4.1 Local baseline

Start a healthy Postgres StateStore, build the local image, and run it:

```bash
cd /path/to/edim/edim-dde-api
make pg-up
make docker-build-local DOCKER_IMAGE=edim-dde-api:aca-dev-local
make docker-run-local DOCKER_IMAGE=edim-dde-api:aca-dev-local
```

In another terminal:

```bash
BASE=http://127.0.0.1:8080 EXPECT_STATE_STORE=postgres make e2e-health
BASE=http://127.0.0.1:8080 EXPECT_STATE_STORE=postgres make e2e-dry
```

The container needs `EDIM_DATABASE_URL` pointing at an address reachable from
inside Docker, normally `host.docker.internal` for a host-published database.
The local image uses a public Python base and is not a substitute for the
production image or enterprise package index.

### 4.2 Azure prerequisites

Platform engineering must provision, per environment:

1. An ACA workload-profile environment in the correct VNet/subnets.
2. An ACR repository and a CI identity allowed to push images.
3. PostgreSQL Flexible Server for StateStore and recommendation persistence.
4. Key Vault for application secrets and private endpoint/DNS as required.
5. A user-assigned or system-assigned managed identity for the Container App.
6. Private connectivity to Databricks, Foundry, Key Vault, PostgreSQL, and
   self-hosted LangSmith if tracing is enabled.
7. Internal ingress or APIM/Easy Auth policy appropriate to the consumers.

Use separate resources and identities for SDBX, DEV, UAT/INTG, and PROD. Do not
reuse a production identity or secret in a lower environment.

### 4.3 Image and registry

Use CI to build and push an immutable image tag. A local example is:

```bash
cd /path/to/edim/edim-dde-api
make vendor-wheels
docker build -f deploy/docker/Dockerfile \
  -t <acr-name>.azurecr.io/edim-dde-api:<git-sha> .
docker push <acr-name>.azurecr.io/edim-dde-api:<git-sha>
```

The production Dockerfile may require the enterprise base image and package
index. A release must record the image digest after push. Deploy the digest or
an immutable commit tag, never `latest`.

### 4.4 Runtime configuration

Set non-secret values in ACA configuration and reference secrets from Key Vault
or ACA secrets. At minimum configure:

```text
EDIM_ENV=dev
PORT=8080
EDIM_STATE_STORE=postgres
EDIM_RECOMMENDATION_STORE=postgres
EDIM_DATABASE_URL=<private-postgres-dsn>
DATABRICKS_HOST=<workspace-host>
DATABRICKS_HTTP_PATH=<warehouse-http-path>
AZURE_OPENAI_ENDPOINT=<foundry-endpoint>
AZURE_OPENAI_DEPLOYMENT_NAME=<deployment>
EDIM_OBSERVABILITY=none|langsmith|mlflow
EDIM_RETRIEVAL=none|azure_ai_search|faiss
```

For self-hosted LangSmith tracing, also set `LANGCHAIN_TRACING_V2`,
`LANGCHAIN_ENDPOINT`, `LANGCHAIN_PROJECT`, and inject
`LANGCHAIN_API_KEY` from Key Vault. Keep the endpoint on the private API URL,
not the browser URL.

Do not set `AZURE_CLIENT_ID` or `AZURE_CLIENT_SECRET` for SQL when using a
managed identity. Those variables can cause `DefaultAzureCredential` to use
the wrong identity. For a user-assigned identity, configure its client ID
through the ACA identity/resource settings according to the platform standard.

### 4.5 Identity and permissions

The ACA runtime identity needs:

- `Key Vault Secrets User` on the selected vault;
- Databricks service-principal registration using the managed identity
  application/client ID;
- `CAN USE` on the SQL warehouse;
- `USE CATALOG`, `USE SCHEMA`, and `SELECT` on the required Unity Catalog
  tables;
- network access to the private PostgreSQL endpoint;
- ACR pull permission if the app uses a user-assigned identity to pull images.

Foundry workload credentials are a separate concern. Prefer a Foundry
application identity or approved Key Vault secret mapping in
`EDIM_FOUNDRY_*`; do not reuse a Databricks SQL token.

### 4.6 ACA deployment shape

The first deployment may be one API Container App. For production, separate
request handling from long-running work:

```text
APIM / internal ingress
        │
        ▼
ACA API (FastAPI, short request)
        │
        ├── PostgreSQL StateStore
        ├── queue/topic
        └── ACA worker or ACA Job (long work / HITL resume)
```

Use HTTP scaling for synchronous traffic and queue/event scaling for workers.
Do not hold a browser or API request open while waiting for human approval.
Persist the state, return a correlation ID, and resume from StateStore.

Configure a health probe against `/health`, target port `8080`, minimum replicas
appropriate to startup latency, and maximum replicas based on Foundry and
warehouse quotas. Validate the platform request timeout against the endpoint’s
worst-case duration.

### 4.7 ACA rollout and validation

For each release:

1. Build, scan, sign, and push the image.
2. Update the DEV Container App to the immutable image digest.
3. Apply environment and secret references.
4. Confirm the managed identity and private DNS paths.
5. Wait for `/health` and verify the expected agent list and stores.
6. Run a dry tuning and RCA request with supplied metrics/evidence.
7. Run one live SQL request using non-sensitive test identifiers.
8. Check Application Insights and, if enabled, the self-hosted LangSmith
   project for the same `X-Request-Id`.
9. Promote the same image digest through UAT/INTG and PROD.

Example checks:

```bash
export BASE=https://<aca-or-apim-host>
curl -fsS "$BASE/health" | python -m json.tool
curl -fsS "$BASE/api/v1/debug/sql-auth" | python -m json.tool
```

Rollback by redeploying the previous approved image digest and restoring its
known-good configuration. Do not rebuild during rollback.

## 4.8 Important distinction: open-source library versus Agent Server

LangChain uses two related but different products. Confusing them can lead to
an incorrect assumption that installing `langgraph` also provides the
production server platform.

| Component | License/availability | What it provides |
|---|---|---|
| **LangGraph open-source framework** | MIT-licensed and free to use | Python/JavaScript graph construction, state transitions, nodes, edges, and application logic |
| **LangGraph Agent Server** | Proprietary LangSmith Deployment software | Standardized APIs for runs, threads, assistants, streaming, persistence, and task-queue execution |
| **Full self-hosted LangSmith Deployment** | Enterprise/licensed platform | Agent Server plus LangSmith control plane, UI, deployment management, observability, and evaluation capabilities |

The open-source package is enough to build and run EDIM’s graph logic inside
the ACA Native FastAPI image. It does **not** automatically provide the
ready-made Agent Server APIs, task orchestration, or managed persistence.

### 4.8.1 What this means for EDIM

- **ACA Native:** uses the free LangGraph library through the EDIM FastAPI
  host. No Agent Server license is required for the graph framework itself.
- **Standalone Agent Server on ACA:** uses the proprietary Agent Server
  runtime. Production self-hosting requires a valid LangSmith license key and
  the applicable Enterprise entitlement. ACA supplies compute; it does not
  supply the Agent Server software or license.
- **Full self-hosted LangSmith on AKS:** uses the licensed LangSmith platform,
  including its control plane and Agent Server. The LangChain platform team
  supplies the version-matched images, Helm/chart artifacts, license process,
  and support requirements.

LangChain provides a local development server for testing, but local
development availability must not be interpreted as a production self-hosting
license. Confirm the entitlement and license-key requirements for the exact
version selected by the platform team.

### 4.8.2 Configuration boundary

Do not mix EDIM’s application tracing variables with Agent Server platform
license variables:

| Concern | Typical variables | Owner |
|---|---|---|
| EDIM graph tracing to self-hosted LangSmith | `LANGCHAIN_TRACING_V2`, `LANGCHAIN_ENDPOINT`, `LANGCHAIN_PROJECT`, `LANGCHAIN_API_KEY` | Application deployment |
| Agent Server platform licensing | `LANGGRAPH_CLOUD_LICENSE_KEY` and the variables required by the approved Agent Server release | LangSmith/platform deployment |
| Agent Server traces | The release’s documented `LANGSMITH_*` endpoint/key settings | Application/platform integration |

The exact Agent Server variable names and license entitlements are
version-dependent. Store license keys and API keys in Key Vault or the
platform secret store; never put them in YAML, a Dockerfile, `langgraph.json`,
or source control.

!!! note "Optional reading"
    See [LangGraph open-source FAQ](https://docs.langchain.com/langsmith/faq),
    [Agent Server](https://docs.langchain.com/langsmith/agent-server), and
    [Self-host standalone servers](https://docs.langchain.com/langsmith/deploy-standalone-server).
    Continue to Target B below for the EDIM packaging and ACA implications.

## 5. Target B — Standalone Agent Server on ACA (optional)

This target deploys the LangGraph Agent Server runtime without the full
LangSmith control plane. It is useful when consumers need Agent Server APIs
rather than the EDIM-specific FastAPI routes.

### 5.1 What changes

| Area | ACA Native | Standalone Agent Server |
|---|---|---|
| Start command | `uvicorn edim_dde_api.main:app` | Approved LangGraph Agent Server command |
| API contract | EDIM REST routes | Agent Server graph/run/thread APIs |
| Graph import | API lifespan bootstraps agents | `langgraph.json` graph factory |
| State | EDIM StateStore configuration | Agent Server PostgreSQL/checkpoint configuration |
| Streaming/runs | Implemented by EDIM API as needed | Provided by Agent Server |
| Control plane/UI | None | None; use self-hosted LangSmith separately if needed |

The Agent Server image must include the Agent Server runtime, the three EDIM
packages, packaged YAML/content, and only the approved graph factories. It must
not depend on a developer’s editable checkout.

### 5.2 Packaging procedure

This procedure becomes executable once the runtime dependency and manifest are
added:

1. Add and pin the approved Agent Server package/CLI in the target dependency
   set.
2. Add `langgraph.json` with an importable graph factory.
3. Add every selected graph factory to an allowlist and test it from a clean
   environment.
4. Build the three wheels and install them into the Agent Server image.
5. Copy immutable YAML, prompt, and skill content into the image or package.
6. Build and scan a separate Agent Server image; do not change the ACA Native
   image’s start command implicitly.
7. Configure external PostgreSQL and Redis according to the approved Agent
   Server version.
8. Deploy the image as a private ACA app with internal ingress unless external
   access is explicitly required.

### 5.3 Runtime configuration and validation

Configure the Agent Server’s documented database, Redis, authentication,
logging, and tracing variables from Key Vault/ACA secrets. Keep the EDIM
environment variables (`EDIM_ENV`, Foundry, Databricks, retrieval, and
LangSmith tracing) consistent with ACA Native.

Validate, in order:

1. The Agent Server reports ready.
2. The `cluster_tuning` graph appears in the configured graph list.
3. A flat input produces a flat output without a `data` key.
4. A second call can resume the same thread/run.
5. A failed run is visible in the selected self-hosted LangSmith project, if
   tracing is enabled.
6. PostgreSQL and Redis survive a pod/container restart.

Do not advertise this target as production-ready until the manifest, runtime
dependency, backing-service configuration, and deployment pipeline exist.

## 6. Target C — Full self-hosted LangSmith Deployment on AKS (optional)

This target is a platform installation, not just another copy of the API
container. It includes the LangSmith control plane/UI and its Agent Server
capabilities inside the enterprise Azure boundary.

### 6.1 Platform prerequisites

The platform team must confirm with LangChain/LangSmith:

- enterprise license, version, support channel, and upgrade policy;
- supported AKS and Kubernetes versions;
- required LangSmith services and resource sizing;
- PostgreSQL, Redis, object/blob storage, and any analytics store requirements;
- license/beacon egress requirements or approved offline procedure;
- private ingress, certificates, DNS, and Entra integration;
- Key Vault/CSI secret delivery and rotation;
- backup, restore, retention, PII deletion, and disaster recovery objectives.

Use the vendor’s version-matched Helm chart and values. Do not copy a SaaS
endpoint or invent chart values from a different release.

### 6.2 Installation sequence

1. Create a dedicated AKS namespace and workload identity.
2. Provision and validate private backing services before installing the
   control plane.
3. Create the LangSmith license/API secrets in Key Vault and map them through
   the approved CSI or workload identity mechanism.
4. Apply the vendor chart/manifest from a pinned release artifact.
5. Configure private ingress, TLS, Entra/RBAC, project/workspace boundaries,
   retention, and redaction policies.
6. Run the vendor health checks and create one tracing project per EDIM
   environment.
7. Deploy the EDIM Agent Server bundle using the approved graph manifest, or
   connect ACA Native tracing to the self-hosted API endpoint.
8. Run a dry graph invocation, confirm the trace, then test restart and restore
   procedures.

### 6.3 EDIM integration modes

Full self-hosted LangSmith can coexist with ACA Native:

```text
ACA Native API ── traces ──► self-hosted LangSmith API on AKS
       │
       └── business calls ──► Databricks / Foundry / PostgreSQL
```

Or it can host the Agent Server runtime on AKS:

```text
Self-hosted LangSmith control plane + Agent Server
       │
       └── packaged EDIM YAML graph factories
```

In both cases, `LANGCHAIN_ENDPOINT` must be the private LangSmith API URL and
the API key must come from that self-hosted instance. A healthy EDIM API does
not prove that trace ingestion, retention, or the LangSmith UI is healthy;
check both planes independently.

### 6.4 Operations

The owning platform team must document:

- chart/image version upgrades and rollback;
- database and object-store backups;
- Redis recovery expectations;
- AKS node-pool and pod disruption strategy;
- alerting for ingestion lag, failed workers, disk growth, and queue depth;
- trace retention and PII deletion;
- project/RBAC administration;
- a quarterly restore exercise.

Application engineers own the EDIM graph package and its compatibility tests.
They do not manually edit production LangSmith pods or backing databases.

## 7. CI/CD release checklist

Every target uses the same promotion gates:

```text
YAML/schema tests
  → unit and graph-shape tests
  → build/version wheels
  → security scan
  → build immutable target artifact
  → deploy SDBX/DEV
  → health + dry smoke
  → live integration smoke
  → approval
  → promote same artifact
```

The pipeline must record:

- Git commit and package versions;
- YAML/content checksum;
- image digest or wheel hashes;
- target and `EDIM_ENV`;
- configuration revision;
- smoke-test request IDs;
- rollback artifact.

A host adapter failure must not require changing the agent YAML. If it does,
stop and review the portability contract.

## 8. Troubleshooting

| Symptom | First checks |
|---|---|
| `/health` is unavailable | Container logs, port `8080`, startup probe, Key Vault/network DNS |
| ACA SQL fails | Managed identity registration, warehouse `CAN USE`, UC grants, private egress |
| Local container cannot reach Postgres | Use `host.docker.internal` or the Compose service name, not `localhost` inside the container |
| Agent Server cannot import a graph | Manifest path, package installation, YAML package data, allowlisted factory |
| Agent Server loses threads | PostgreSQL/checkpointer configuration and persistence |
| Agent Server streaming fails | Redis/backing service, ingress timeout, target-specific runtime version |
| No LangSmith traces | Private API DNS, endpoint `/api/v1`, instance-issued key, `LANGCHAIN_TRACING_V2` |
| Traces contain sensitive text | Apply the PII policy before invocation; logs and LangSmith payloads are separate |
| New YAML is missing in a deployment | Rebuild wheels/image; do not rely on an old editable install or mutable volume |

## Related documentation

- [Deploy & hosting](deploy-and-hosting.md) — existing Apps, Docker, and ACA commands
- [Packaging](../contribute/packaging.md) — package versions and wheel publication
- [Agent package layout](../build-agents/agent-package-layout.md) — YAML and Python layout
- [Agent deployment & composition](../architecture/agent-deployment-and-composition.md) — one vs many agents
- [Environments](../platform/environments.md) — SDBX/DEV/PROD settings
- [Observability](../platform/observability.md) — provider selection
- [LangSmith setup](../platform/langsmith-setup.md) — tracing and self-hosted endpoint
- [Live smoke](../contribute/live-smoke-test.md) — API validation
- [Environment variables](../reference/env-vars.md) — complete variable catalog
