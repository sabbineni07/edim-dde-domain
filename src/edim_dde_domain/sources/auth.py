"""Databricks SQL access tokens — host-agnostic resolution.

1. **Databricks Apps:** API middleware reads user OAuth from
   ``X-Forwarded-Access-Token`` and calls ``set_request_databricks_token``.
2. **Else (local, ACA, Docker, …):** ``DefaultAzureCredential``
   (``az login``, managed identity). Do **not** put Foundry SP in
   ``AZURE_CLIENT_*`` — use ``EDIM_FOUNDRY_*`` instead.

``Authorization: Bearer`` is intentionally ignored so API-level auth (if
added later) is never forwarded to Databricks SQL as the user token.

See docs/platform/access-and-permissions.md for per-host identity matrix.
"""

from __future__ import annotations

import logging
import os
from contextvars import ContextVar, Token
from typing import Any, Mapping, Optional

from edim_dde_domain.errors import DatabricksNotConfiguredError

logger = logging.getLogger(__name__)

# Azure Databricks first-party app scope (same as `az account get-access-token --resource …`)
DATABRICKS_AAD_SCOPE = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default"

_FORWARDED_TOKEN_HEADERS = (
    "x-forwarded-access-token",
    "X-Forwarded-Access-Token",
)

_request_databricks_token: ContextVar[Optional[str]] = ContextVar(
    "request_databricks_token", default=None
)


def is_databricks_apps_runtime() -> bool:
    """True when process env looks like a Databricks Apps host."""
    if (os.environ.get("DATABRICKS_APP_PORT") or "").strip():
        return True
    # Apps injects these for the app service principal
    if (os.environ.get("DATABRICKS_CLIENT_ID") or "").strip() and (
        os.environ.get("DATABRICKS_CLIENT_SECRET") or ""
    ).strip():
        return True
    return False


def _header_value(headers: Mapping[str, Any], name: str) -> Optional[str]:
    key = name.lower()
    for header_name, value in headers.items():
        if str(header_name).lower() == key:
            if isinstance(value, (list, tuple)):
                return str(value[0]).strip() if value else None
            return str(value).strip() if value is not None else None
    return None


def extract_forwarded_databricks_token(headers: Mapping[str, Any]) -> Optional[str]:
    """Read user OAuth from Databricks Apps gateway forwarded header only.

    Does not read ``Authorization`` — that header is reserved for API auth.
    Used by API middleware before ``set_request_databricks_token``.
    """
    for name in _FORWARDED_TOKEN_HEADERS:
        token = _header_value(headers, name)
        if token:
            return token
    return None


def set_request_databricks_token(token: Optional[str]) -> Token:
    """Bind a request-scoped user token (Apps middleware)."""
    return _request_databricks_token.set((token or "").strip() or None)


def reset_request_databricks_token(ctx: Token) -> None:
    _request_databricks_token.reset(ctx)


def get_request_databricks_token() -> Optional[str]:
    return _request_databricks_token.get()


def get_azure_databricks_token() -> str:
    """Token via DefaultAzureCredential (``az login``, Managed Identity, etc.)."""
    try:
        from azure.identity import DefaultAzureCredential

        token = DefaultAzureCredential().get_token(DATABRICKS_AAD_SCOPE)
        access = (token.token or "").strip()
        if not access:
            raise DatabricksNotConfiguredError(
                "Azure credential returned an empty Databricks token"
            )
        return access
    except ImportError as exc:
        raise DatabricksNotConfiguredError(
            "azure-identity is required for local Databricks auth. "
            "Install with: pip install 'edim-dde-domain[azure]' "
            "or pip install azure-identity"
        ) from exc
    except DatabricksNotConfiguredError:
        raise
    except Exception as exc:
        raise DatabricksNotConfiguredError(
            "Failed to obtain Databricks token via DefaultAzureCredential "
            f"({type(exc).__name__}: {exc}). "
            "Local: run `az login`. "
            "Databricks Apps: ensure middleware sets X-Forwarded-Access-Token. "
            "ACA/Docker: ensure managed identity (or a dedicated SQL SP) can "
            "access the workspace — do not reuse Foundry EDIM_FOUNDRY_* via "
            "AZURE_CLIENT_* (see docs/platform/access-and-permissions.md)."
        ) from exc


def resolve_access_token(*, source_name: str = "") -> str:
    """Resolve a SQL warehouse access token.

    1. Request-scoped user OAuth (Databricks Apps → API middleware)
    2. Else DefaultAzureCredential (local ``az login``, ACA MI)

    On Databricks Apps, missing ``X-Forwarded-Access-Token`` is a hard error
    unless ``EDIM_ALLOW_APPS_AZURE_SQL_FALLBACK=1`` (debug only).
    """
    label = source_name or "source"

    scoped = get_request_databricks_token()
    if scoped:
        logger.debug("databricks_token_from_request_scope", extra={"source": label})
        return scoped

    # On Apps, do not silently fall back to DefaultAzureCredential (az login / MI).
    # That path is for local/ACA and produced confusing OpenSession errors when the
    # gateway did not forward a user token. Escape hatch for rare debug only:
    # EDIM_ALLOW_APPS_AZURE_SQL_FALLBACK=1 — leave unset in normal Apps deploys.
    allow_apps_azure_fallback = (
        os.environ.get("EDIM_ALLOW_APPS_AZURE_SQL_FALLBACK") or ""
    ).strip().lower() in ("1", "true", "yes")
    if is_databricks_apps_runtime() and not allow_apps_azure_fallback:
        raise DatabricksNotConfiguredError(
            f"Source {label!r}: no X-Forwarded-Access-Token on this request. "
            "On Databricks Apps, SQL requires the gateway-injected user token. "
            "If scope `sql` is already set: open the App URL (e.g. /docs), "
            "re-consent if prompted, call GET /api/v1/debug/sql-auth and confirm "
            "forwarded_access_token_present=true; ensure your user has CAN USE "
            "on the warehouse + SELECT on UC tables. "
            "See docs/platform/access-and-permissions.md."
        )

    logger.debug("databricks_token_via_azure_credential", extra={"source": label})
    return get_azure_databricks_token()
