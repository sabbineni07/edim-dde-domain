# Part G — API host

**Learning path:** G0 · [Preface](../README.md)  
**← Previous:** [External plugins](../build-agents/external-plugins.md) · **Next:** [Configuration](configuration.md) →

## Chapter overview

Part G documents **`edim-dde-api`**: environment configuration, HTTP surface, and deployment targets (Databricks Apps default, Docker, Azure Container Apps).

**After completing Part G you will:**

- Configure a minimal working API for local and Apps hosts.
- Invoke bundled agents via `/api/v1/*` and interpret OpenAPI models.
- Package wheels, sync bundles, and deploy with stop/start semantics.

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
| **G3** | [Deploy & hosting](deploy-and-hosting.md) | Apps, Docker, ACA |

---

## Host comparison

| Host | SQL identity | Typical first use |
|------|--------------|-------------------|
| **Local uvicorn + Docker Postgres** | `az login` on host | Developer smoke |
| **Databricks Apps** | User `X-Forwarded-Access-Token` | DEV/PROD API |
| **Azure Container Apps** | Container managed identity | Portable container deploy |

!!! note "Engineer guide (`/guide`)"
    MkDocs HTML is **local Docker** or **optional Apps mount** (`EDIM_MOUNT_GUIDE=1`). It is not required for agent runtime.

---

## Summary

Configure (**G1**), validate endpoints (**G2**), then deploy (**G3**).

**Next →** [Configuration (G1)](configuration.md)
