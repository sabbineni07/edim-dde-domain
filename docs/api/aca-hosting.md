# Host the API and engineer guide on Azure Container Apps

**Learning path:** G3b · [Preface](../README.md)  
**← Previous:** [Deploy and hosting](./deploy-and-hosting.md) · **Next:** [Environment variables](../reference/env-vars.md) →

## Chapter summary

Step-by-step for the **standard host**: one container on Azure Container Apps (ACA) that serves the FastAPI API and the engineer guide. Use this when Databricks Apps cannot satisfy Conditional Access, because Apps run on shared serverless compute and cannot egress through your VNet NAT.

**Outcome:** `https://<aca-host>/health`, `/api/v1/*`, `/docs`, and `/guide/` answer from a container whose Entra sign-in source IP is your NAT gateway.

---

## 1. What you are hosting

| Surface | Path | Where it comes from |
|---------|------|---------------------|
| API | `/api/v1/*` (`/health`, RCA, tuning, directory, A2A invoke) | `edim-dde-api` |
| OpenAPI | `/docs` | FastAPI |
| Engineer guide | `/guide/` | MkDocs site baked into the image (`deploy/docker/guide-site`) |

There is no separate product SPA in this repo. The image `deploy/docker/Dockerfile` copies the guide and sets `EDIM_GUIDE_SITE_DIR`. On ACA the guide mounts automatically (Databricks Apps hide it unless `EDIM_MOUNT_GUIDE=1`).

Template: `edim-dde-api/deploy/azure/aca-native/main.bicep`.

---

## 2. Why ACA, not Databricks Apps

| | Databricks Apps | ACA in your VNet |
|--|-----------------|------------------|
| Compute | Databricks-managed serverless | Your Container Apps environment |
| Source IP Entra sees | Shared serverless pool | NAT gateway on your subnet |
| Conditional Access location rule | Fails with `AADSTS53003` | Passes when the NAT IP is a trusted named location |
| VNet injection | Not supported for Apps | `infrastructureSubnetId` on the managed environment |

Do not plan to fix Apps by allowlisting Databricks serverless IP ranges. Those ranges are shared and change. Front-end Private Link, NCC egress policies, and private endpoints do not make `login.microsoftonline.com` see your VNet address. The private network gateway (beta) applies to serverless Databricks Runtime products, not Databricks Apps.

---

## 3. Target network

```text
Users / APIM
    │  HTTPS
    ▼
ACA managed environment  (infrastructure subnet in your VNet)
    │  egress via NAT gateway (trusted public IP)
    ├── login.microsoftonline.com     Foundry token (EDIM_FOUNDRY_*)
    ├── Foundry / Azure OpenAI
    ├── Databricks SQL warehouse + UC (managed identity)
    ├── Key Vault (private endpoint preferred)
    └── PostgreSQL Flexible Server (private endpoint)
```

Platform must create, in the same region as the workspace you call:

1. **VNet** with a dedicated **infrastructure subnet** for ACA. Delegate it to `Microsoft.App/environments`. Minimum size is `/27`; use `/23` when the environment will grow. Do not share the subnet with other workloads.
2. **NAT gateway** attached to that subnet, with a **static public IP** that is already in the Entra trusted named location (the same location that allows the VNet-injected cluster).
3. **Private endpoints + private DNS** for Key Vault and PostgreSQL.
4. Outbound path to the Databricks workspace SQL hostname and to Foundry. If those must stay private, add private endpoints; the Entra login itself stays a public Microsoft endpoint reached **from** the NAT IP.
5. **NSG**: allow the ACA subnet outbound HTTPS (443) to those destinations. Do not rely on a public ACA environment with no VNet if Conditional Access is in force.

Internal ingress (`internal: true` in the Bicep parameter `internalIngress`) is the production default. Put APIM or another private front door in front if users outside the VNet must call the API. External ingress is only for a temporary lab.

---

## 4. Identities (do not mix them)

| Identity | Env | Used for |
|----------|-----|----------|
| **A — ACA managed identity** | user-assigned MI on the Container App. Do **not** set `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` | Key Vault, ACR pull, Databricks SQL / UC |
| **B — Foundry app registration** | `EDIM_FOUNDRY_TENANT_ID`, `EDIM_FOUNDRY_CLIENT_ID`, `EDIM_FOUNDRY_CLIENT_SECRET` from Key Vault | Foundry token scope `https://ai.azure.com/.default` |

`DefaultAzureCredential` on ACA is the managed identity only when `AZURE_CLIENT_*` are unset. If you copy the notebook's `AZURE_CLIENT_ID` into the container, SQL stops using the MI.

The Foundry app (identity B) still uses client credentials. Conditional Access must allow **that** service principal **from the NAT IP**. A policy that only allows interactive users will still return `AADSTS53003`.

---

## 5. Prerequisites checklist

- [ ] Resource group and region chosen (match Databricks workspace region).
- [ ] VNet, ACA infrastructure subnet, NAT gateway, trusted public IP.
- [ ] ACR (admin user disabled).
- [ ] Key Vault (RBAC, public network disabled) with secrets:
  - `edim-database-url`
  - `edim-foundry-tenant-id`
  - `edim-foundry-client-id`
  - `edim-foundry-client-secret`
- [ ] PostgreSQL Flexible Server, private endpoint, database `edim`.
- [ ] Foundry project endpoint, deployment name, and RBAC for identity B.
- [ ] Databricks workspace host and SQL warehouse HTTP path.
- [ ] Permission to assign the MI as a Databricks service principal.

---

## 6. Deploy steps

### 6.1 Build the image (API + guide)

From `edim-dde-api/` on a machine that can reach your package index:

```bash
make vendor-wheels          # ai + domain + api wheels and MkDocs site
docker build -f deploy/docker/Dockerfile \
  -t <acr-name>.azurecr.io/edim-dde-api:<git-sha> .
az acr login --name <acr-name>
docker push <acr-name>.azurecr.io/edim-dde-api:<git-sha>
```

Record the **digest**. Deploy the digest or the immutable `<git-sha>` tag, never `latest`.

The Dockerfile listens on `PORT` (default `8080`) and sets `EDIM_GUIDE_SITE_DIR=/app/guide-site`.

### 6.2 Foundation (identity, ACR, vault, environment)

`deploy/azure/aca-native/main.bicep` creates the user-assigned identity, ACR, Key Vault (RBAC, no public access), Log Analytics, and the Container Apps environment. It creates the Container App only when `deployContainerApp=true`.

Create the vault secrets **before** the app revision. The Bicep references them by name; it does not upload secret values.

```bash
az deployment group create \
  --resource-group <rg> \
  --template-file deploy/azure/aca-native/main.bicep \
  --parameters \
    edimEnvironment=dev \
    acrName=<acr-name> \
    containerAppsEnvironmentName=<env-name> \
    containerAppName=<app-name> \
    runtimeIdentityName=<mi-name> \
    keyVaultName=<vault-name> \
    infrastructureSubnetId=<aca-subnet-resource-id> \
    internalIngress=true \
    image=<acr-name>.azurecr.io/edim-dde-api@sha256:<digest> \
    deployContainerApp=false
```

Copy `runtimeIdentityPrincipalId` and `runtimeIdentityClientId` from the deployment outputs (client ID is on the identity resource). Grant that principal **Key Vault Secrets User** (the template assigns it on the vault it creates) and **AcrPull** (also assigned when the template creates ACR).

### 6.3 Databricks grants for the managed identity

Same sequence as [Deploy & hosting](./deploy-and-hosting.md), section **6.4 ACA SQL — grant managed identity warehouse + UC**:

1. Entra application (client) ID of the user-assigned MI.
2. Databricks account → service principals → add that client ID → workspace.
3. Warehouse permission **Can Use**.
4. Unity Catalog `USE CATALOG`, `USE SCHEMA`, `SELECT` on the metric tables.

### 6.4 Foundry secret and Conditional Access

Store identity B in Key Vault. Confirm Entra sign-in logs for that client ID from the NAT public IP are **not** blocked by the location policy.

If logs still show `AADSTS53003`, the NAT IP is missing from the named location, or the policy does not allow client-credentials for this app. Fix the policy or the named location. Do not switch the container to `AZURE_CLIENT_*`.

### 6.5 Non-secret configuration

Set these on the Container App (plain env, not secrets):

```text
PORT=8080
EDIM_ENV=dev
EDIM_STATE_STORE=postgres
EDIM_CHECKPOINTER=postgres
EDIM_RECOMMENDATION_STORE=postgres
EDIM_OBSERVABILITY=none
DATABRICKS_HOST=<workspace-host>
DATABRICKS_HTTP_PATH=<warehouse-http-path>
AZURE_OPENAI_ENDPOINT=<foundry-project-or-openai-endpoint>
AZURE_OPENAI_DEPLOYMENT_NAME=<deployment>
AZURE_KEY_VAULT_URL=https://<vault-name>.vault.azure.net/
```

Secret refs (already in the Bicep app template):

```text
EDIM_DATABASE_URL          → Key Vault edim-database-url
EDIM_FOUNDRY_TENANT_ID     → edim-foundry-tenant-id
EDIM_FOUNDRY_CLIENT_ID     → edim-foundry-client-id
EDIM_FOUNDRY_CLIENT_SECRET → edim-foundry-client-secret
```

Optional A2A (only if this environment dials other runtimes):

```text
EDIM_A2A_TOKEN=<from Key Vault>
EDIM_A2A_TASK_STORE=file
EDIM_A2A_TASK_DIR=/tmp/edim-a2a-tasks
EDIM_AGENT_RESOLVE=auto
```

File task state on `/tmp` does not survive a replica restart. Use `memory` until a shared store is required. See [ADR-002](../architecture/adr-002-a2a-call-contract.md).

### 6.6 Create the Container App revision

Re-run the deployment with `deployContainerApp=true` and the image digest, or create the app in the portal against the same environment, identity, ingress port **8080**, and secret refs.

Health probe: HTTP `GET /health` on port 8080. Minimum replicas `1` so the guide and API stay warm. Scale on HTTP concurrency (the template uses 20).

Ingress:

- Production: internal, then APIM or private DNS.
- Lab only: external, HTTPS, allow insecure **off**.

### 6.7 Validate

From a network that can reach the ingress:

```bash
export BASE=https://<aca-or-apim-host>
curl -fsS "$BASE/health" | python -m json.tool
curl -fsS -o /dev/null -w "%{http_code}\n" "$BASE/guide/"
curl -fsS "$BASE/api/v1/debug/sql-auth" | python -m json.tool
```

Then one dry tuning or RCA call with metrics or `evidence_pack` supplied (no warehouse), then one live SQL call with a non-sensitive test id. Confirm Foundry returns a completion. In Entra sign-in logs, identity B's token request should show the NAT public IP and success.

| Check | Pass |
|-------|------|
| `/health` | `status=ok`, `state_store=postgres` |
| `/guide/` | `200` and the engineer guide index |
| `/docs` | OpenAPI UI |
| SQL | `/api/v1/debug/sql-auth` shows the MI, not the Foundry client id |
| Foundry | Tuning or RCA completes without `AADSTS53003` |

---

## 7. Rollback

Redeploy the previous image **digest** and the previous env/secret refs.
Do not rebuild during rollback.

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `AADSTS53003` on Foundry | Token request not from a trusted IP, or CA blocks this SP | NAT IP in the named location; CA allows client credentials for identity B |
| SQL uses the wrong app id | `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` set on the container | Remove them; SQL must be the ACA MI |
| `/guide/` 404 | Image built without `make vendor-wheels` / guide-site | Rebuild so `deploy/docker/guide-site` exists, then redeploy the digest |
| `/health` timeout | Probe on the wrong port, or image crash | Target port `8080`; read Log Analytics for the revision |
| Key Vault `Forbidden` | MI missing Secrets User, or public vault blocked without PE | Role assignment + private DNS |
| Warehouse `403` / permission | MI not a Databricks SP, or missing UC grants | [Deploy & hosting](./deploy-and-hosting.md), section 6.4 |

---

## 9. Related

| Doc | Role |
|-----|------|
| [Deployment targets](./deployment-targets.md) | Release checklist and image rules |
| [Deploy & hosting](./deploy-and-hosting.md) | Local Docker / Compose commands; section 6.4 is the MI grant |
| [Authentication flows §4](../platform/authentication-flows.md#4-azure-container-apps-standard-host--mi--kv) | Identity diagram |
| [Key Vault bootstrap](../platform/key-vault-bootstrap.md) | Secret map |
| [ADR-002](../architecture/adr-002-a2a-call-contract.md) | Agent call contract (optional on this host) |

## Summary

- Host **API + `/guide/`** as one ACA container, port 8080.
- Put the environment in **your VNet** and egress through a **NAT IP** Entra trusts.
- **MI** for SQL and Key Vault. **`EDIM_FOUNDRY_*`** for Foundry. Never set `AZURE_CLIENT_*` on the container.

**Next →** [Environment variables](../reference/env-vars.md)

<!-- edim-learning-nav -->
---

← [Deploy and hosting](./deploy-and-hosting.md) · [Environment variables](../reference/env-vars.md) →
