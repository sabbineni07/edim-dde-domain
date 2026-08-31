# Part G — API host

**Learning path:** G0 · [Preface](../README.md)  
**← Previous:** [External plugins](../build-agents/external-plugins.md) · **Next:** [Configuration](configuration.md) →

## Chapter overview

Part G documents **`edim-dde-api`**: environment configuration, HTTP surface,
and deployment targets. ACA Native is the standard host; Standalone Agent
Server on ACA and Full self-hosted LangSmith Deployment on AKS are optional
targets. Databricks Apps remains a compatibility path.

**After completing Part G you will:**

- Configure a minimal working API for local and Apps hosts.
- Invoke bundled agents via `/api/v1/*` and interpret OpenAPI models.
- Package the shared YAML graph artifact and deploy it to the selected host.

---

## Prerequisites

| Requirement | Chapter |
|-------------|---------|
| Platform planes | [Part C overview](../platform/index.md) |
| Request lifecycle | [Request flow (B6)](../architecture/request-flow.md) |

---

## Chapters in this part

| Step | Chapter | Topic |
|------|---------|-------|
| **G1** | [Configuration](configuration.md) | Required env vars |
| **G2** | [HTTP endpoints](endpoints.md) | OpenAPI surface |
| **G3a** | [Deployment targets and release runbook](deployment-targets.md) | Target selection, packaging, rollout |
| **G3** | [Deploy & hosting](deploy-and-hosting.md) | Apps, Docker, ACA compatibility commands |

---

## Host comparison

| Host | SQL identity | Typical first use |
|------|--------------|-------------------|
| **Local uvicorn + Docker Postgres** | `az login` on host | Developer smoke |
| **ACA Native** | Container managed identity | Standard DEV/PROD API |
| **Standalone Agent Server on ACA** | ACA identity + Agent Server config | LangGraph runs/threads/streaming |
| **Full self-hosted LangSmith on AKS** | AKS workload identity | Private LangSmith platform |
| **Databricks Apps** | User `X-Forwarded-Access-Token` | Compatibility/data-local workloads |

!!! note "Engineer guide (`/guide`)"
    MkDocs HTML is **local Docker** or **optional Apps mount** (`EDIM_MOUNT_GUIDE=1`). It is not required for agent runtime.

---

## Summary

Configure (**G1**), validate endpoints (**G2**), then deploy (**G3**).

**Next →** [Configuration (G1)](configuration.md)
