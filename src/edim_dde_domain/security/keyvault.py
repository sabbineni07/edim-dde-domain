"""Azure Key Vault secret bootstrap (BL-013).

Loads mapped secrets into ``os.environ`` without overwriting values already set
(so local ``.env`` wins). Uses ``DefaultAzureCredential``.
"""

from __future__ import annotations

import logging
import os
from typing import Mapping

logger = logging.getLogger(__name__)

_DEFAULT_SECRET_MAP: dict[str, str] = {
    "azure-client-id": "AZURE_CLIENT_ID",
    "azure-client-secret": "AZURE_CLIENT_SECRET",
    "azure-tenant-id": "AZURE_TENANT_ID",
    "langchain-api-key": "LANGCHAIN_API_KEY",
}


def parse_secret_map(raw: str | None) -> dict[str, str]:
    """Parse ``vaultSecret:ENV_VAR,vaultSecret2:ENV_VAR2`` pairs."""
    if not raw or not raw.strip():
        return dict(_DEFAULT_SECRET_MAP)
    out: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(
                f"Invalid EDIM_KV_SECRET_MAP entry {part!r}; expected secret:ENV_VAR"
            )
        secret_name, env_name = part.split(":", 1)
        secret_name, env_name = secret_name.strip(), env_name.strip()
        if not secret_name or not env_name:
            raise ValueError(f"Invalid EDIM_KV_SECRET_MAP entry {part!r}")
        out[secret_name] = env_name
    return out


def load_key_vault_secrets(
    *,
    vault_url: str | None = None,
    secret_map: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Fetch secrets and set missing env vars. Returns env names that were set."""
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
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
    except ImportError as exc:
        raise RuntimeError(
            "Key Vault bootstrap requires azure-identity and azure-keyvault-secrets. "
            "Install: pip install 'edim-dde-domain[azure,keyvault]'"
        ) from exc

    client = SecretClient(vault_url=url, credential=DefaultAzureCredential())
    loaded: dict[str, str] = {}
    for secret_name, env_name in mapping.items():
        if os.environ.get(env_name):
            logger.debug("Env %s already set; not overwriting from Key Vault", env_name)
            continue
        secret = client.get_secret(secret_name)
        if secret.value is None:
            logger.warning("Key Vault secret %s has no value", secret_name)
            continue
        os.environ[env_name] = secret.value
        loaded[env_name] = secret_name
        logger.info("Loaded Key Vault secret %s → env %s", secret_name, env_name)
    return loaded
