"""Azure Key Vault secret bootstrap (BL-013).

Business purpose
----------------
At process start, fetch mapped vault secrets into ``os.environ`` so Foundry
and other clients see credentials without baking secrets into images. The
credential used to *open* the vault is chosen separately from Foundry
``EDIM_FOUNDRY_*`` values written *from* the vault (see ``_vault_credential``)
so Apps SP / MI, Foundry SP, and SQL auth do not collide via ``AZURE_CLIENT_*``.

Public API
----------
* ``parse_secret_map`` — parse ``EDIM_KV_SECRET_MAP`` or return defaults
* ``load_key_vault_secrets`` — fetch + set env (no-op if vault URL unset)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping

logger = logging.getLogger(__name__)

# Env var → vault secret name. Foundry SP goes to EDIM_FOUNDRY_* (not AZURE_CLIENT_*)
# so DefaultAzureCredential for SQL does not pick up the Foundry workload SP.
_DEFAULT_SECRET_MAP: dict[str, str] = {
    "EDIM_FOUNDRY_CLIENT_ID": "azure-client-id",
    "EDIM_FOUNDRY_CLIENT_SECRET": "azure-client-secret",
    "EDIM_FOUNDRY_TENANT_ID": "azure-tenant-id",
    "LANGCHAIN_API_KEY": "langchain-api-key",
}


def parse_secret_map(raw: str | None) -> dict[str, str]:
    """Parse ``ENV_VAR:vaultSecret,OTHER_ENV:otherSecret`` pairs.

    Args:
        raw: Comma-separated map string, or empty/None for the built-in default.

    Returns:
        ``{env_name: vault_secret_name}``.

    Raises:
        ValueError: Malformed entry (missing ``:`` or empty names).
    """
    if not raw or not raw.strip():
        return dict(_DEFAULT_SECRET_MAP)
    out: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(
                f"Invalid EDIM_KV_SECRET_MAP entry {part!r}; "
                "expected ENV_VAR:vaultSecretName"
            )
        env_name, secret_name = part.split(":", 1)
        env_name, secret_name = env_name.strip(), secret_name.strip()
        if not env_name or not secret_name:
            raise ValueError(f"Invalid EDIM_KV_SECRET_MAP entry {part!r}")
        out[env_name] = secret_name
    return out


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _vault_credential() -> tuple[Any, str]:
    """Return (credential, source_label) for talking to Key Vault.

    Order:
    1. Explicit vault-reader SP: ``EDIM_KV_CLIENT_ID`` + ``EDIM_KV_CLIENT_SECRET``
       + tenant (``EDIM_KV_TENANT_ID`` or ``AZURE_TENANT_ID``)
    2. Databricks Apps SP: ``DATABRICKS_CLIENT_ID`` + ``DATABRICKS_CLIENT_SECRET``
       + ``AZURE_TENANT_ID`` (tenant is not secret; required for client-credentials)
    3. ``DefaultAzureCredential`` (local ``az login``, ACA managed identity, …)
    """
    from azure.identity import ClientSecretCredential, DefaultAzureCredential

    kv_id = (os.environ.get("EDIM_KV_CLIENT_ID") or "").strip()
    kv_secret = (os.environ.get("EDIM_KV_CLIENT_SECRET") or "").strip()
    kv_tenant = (
        os.environ.get("EDIM_KV_TENANT_ID") or os.environ.get("AZURE_TENANT_ID") or ""
    ).strip()
    if kv_id and kv_secret and kv_tenant:
        return (
            ClientSecretCredential(
                tenant_id=kv_tenant, client_id=kv_id, client_secret=kv_secret
            ),
            "EDIM_KV_CLIENT_*",
        )

    dbx_id = (os.environ.get("DATABRICKS_CLIENT_ID") or "").strip()
    dbx_secret = (os.environ.get("DATABRICKS_CLIENT_SECRET") or "").strip()
    tenant = (os.environ.get("AZURE_TENANT_ID") or "").strip()
    if dbx_id and dbx_secret and tenant:
        return (
            ClientSecretCredential(
                tenant_id=tenant, client_id=dbx_id, client_secret=dbx_secret
            ),
            "DATABRICKS_CLIENT_* (Apps SP)",
        )
    if dbx_id and dbx_secret and not tenant:
        logger.warning(
            "DATABRICKS_CLIENT_ID/SECRET present but AZURE_TENANT_ID unset; "
            "cannot use Apps SP for Key Vault — falling back to DefaultAzureCredential"
        )

    return DefaultAzureCredential(), "DefaultAzureCredential"


def _should_set_env(env_name: str) -> bool:
    """Whether to write ``env_name`` from a vault secret.

    Existing local ``.env`` / explicit inject wins unless ``EDIM_KV_FORCE=1``.
    """
    existing = (os.environ.get(env_name) or "").strip()
    if not existing:
        return True
    if _truthy("EDIM_KV_FORCE"):
        return True
    # Local .env / explicit inject wins by default
    logger.debug("Env %s already set; not overwriting from Key Vault", env_name)
    return False


def load_key_vault_secrets(
    *,
    vault_url: str | None = None,
    secret_map: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Fetch secrets and set env vars.

    ``secret_map`` / ``EDIM_KV_SECRET_MAP`` use ``{env_name: vault_secret_name}``.
    No-ops (returns ``{}``) when ``AZURE_KEY_VAULT_URL`` is unset.

    Args:
        vault_url: Override vault URL; default ``AZURE_KEY_VAULT_URL``.
        secret_map: Override map; default parsed from ``EDIM_KV_SECRET_MAP``.

    Returns:
        ``{env_name: vault_secret_name}`` for secrets actually loaded.

    Raises:
        RuntimeError: azure-keyvault-secrets / azure-identity not installed.
    """
    url = (vault_url or os.environ.get("AZURE_KEY_VAULT_URL") or "").strip()
    if not url:
        logger.debug("AZURE_KEY_VAULT_URL not set; skipping Key Vault bootstrap")
        return {}

    mapping = (
        dict(secret_map)
        if secret_map is not None
        else parse_secret_map(os.environ.get("EDIM_KV_SECRET_MAP"))
    )
    if not mapping:
        return {}

    try:
        from azure.keyvault.secrets import SecretClient
    except ImportError as exc:
        raise RuntimeError(
            "Key Vault bootstrap requires azure-identity and azure-keyvault-secrets. "
            "Install: pip install 'edim-dde-domain[azure,keyvault]'"
        ) from exc

    credential, source = _vault_credential()
    logger.info("Key Vault auth via %s → %s", source, url)
    client = SecretClient(vault_url=url, credential=credential)

    loaded: dict[str, str] = {}
    for env_name, secret_name in mapping.items():
        if not _should_set_env(env_name):
            continue
        secret = client.get_secret(secret_name)
        if secret.value is None:
            logger.warning("Key Vault secret %s has no value", secret_name)
            continue
        os.environ[env_name] = secret.value
        loaded[env_name] = secret_name
        logger.info("Loaded Key Vault secret %s → env %s", secret_name, env_name)
    return loaded
