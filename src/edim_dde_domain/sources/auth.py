"""Resolve Databricks SQL access tokens for named sources."""

from __future__ import annotations

import logging
import os
from typing import Mapping, Optional

from edim_dde_domain.errors import DatabricksNotConfiguredError

logger = logging.getLogger(__name__)

# Azure Databricks first-party app scope (same as `az account get-access-token --resource …`)
DATABRICKS_AAD_SCOPE = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default"

SUPPORTED_AUTH_MODES = frozenset({"auto", "env_token", "azure_credential"})


def _env_token(token_env: str, environ: Mapping[str, str]) -> str:
    return (environ.get(token_env) or "").strip()


def get_azure_databricks_token() -> str:
    """Token via DefaultAzureCredential (az login, Managed Identity, App SP, etc.).

    If ``AZURE_TENANT_ID`` + ``AZURE_CLIENT_ID`` + ``AZURE_CLIENT_SECRET`` are set,
    uses ``ClientSecretCredential`` first (same pattern as the product app).
    """
    tenant_id = (os.environ.get("AZURE_TENANT_ID") or "").strip()
    client_id = (os.environ.get("AZURE_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("AZURE_CLIENT_SECRET") or "").strip()

    try:
        if tenant_id and client_id and client_secret:
            from azure.identity import ClientSecretCredential

            cred = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )
        else:
            from azure.identity import DefaultAzureCredential

            cred = DefaultAzureCredential()

        token = cred.get_token(DATABRICKS_AAD_SCOPE)
        access = (token.token or "").strip()
        if not access:
            raise DatabricksNotConfiguredError(
                "Azure credential returned an empty Databricks token"
            )
        return access
    except ImportError as exc:
        raise DatabricksNotConfiguredError(
            "azure-identity is required for Azure credential auth. "
            "Install with: pip install 'edim-dde-domain[azure]' "
            "or pip install azure-identity"
        ) from exc
    except DatabricksNotConfiguredError:
        raise
    except Exception as exc:
        raise DatabricksNotConfiguredError(
            "Failed to obtain Databricks token via Azure credential "
            f"({type(exc).__name__}: {exc}). "
            "Run `az login` or set AZURE_CLIENT_ID/SECRET/TENANT_ID, "
            "or set DATABRICKS_TOKEN."
        ) from exc


def resolve_access_token(
    *,
    auth_mode: str = "auto",
    token_env: str = "DATABRICKS_TOKEN",
    environ: Optional[Mapping[str, str]] = None,
    source_name: str = "",
) -> str:
    """Resolve a SQL warehouse access token.

    Modes:
    - ``auto`` (default): env token if set, else DefaultAzureCredential
    - ``env_token``: require ``token_env`` only
    - ``azure_credential``: Azure identity only
    """
    env = environ if environ is not None else os.environ
    mode = (auth_mode or "auto").strip().lower()
    if mode not in SUPPORTED_AUTH_MODES:
        raise DatabricksNotConfiguredError(
            f"Unsupported auth.mode {auth_mode!r} for source {source_name!r}. "
            f"Use one of: {sorted(SUPPORTED_AUTH_MODES)}"
        )

    label = source_name or "source"

    if mode in ("auto", "env_token"):
        token = _env_token(token_env, env)
        if token:
            logger.debug(
                "databricks_token_from_env",
                extra={"source": label, "env": token_env},
            )
            return token
        if mode == "env_token":
            raise DatabricksNotConfiguredError(
                f"Source {label!r} auth.mode=env_token requires {token_env} to be set"
            )

    logger.debug(
        "databricks_token_via_azure_credential",
        extra={"source": label, "mode": mode},
    )
    return get_azure_databricks_token()
