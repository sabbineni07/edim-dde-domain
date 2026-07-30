"""Databricks SQL access tokens — two paths only.

1. **Databricks Apps (deployed):** API middleware reads user OAuth from
   ``X-Forwarded-Access-Token`` and calls ``set_request_databricks_token``.
2. **Local dev:** ``DefaultAzureCredential`` after ``az login``.

Extend later if CI / service-principal hosting is needed.
"""

from __future__ import annotations

import logging
import re
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

_STUB_AUTH_RE = re.compile(r"^Bearer\s+stub-token-", re.IGNORECASE)

_request_databricks_token: ContextVar[Optional[str]] = ContextVar(
    "request_databricks_token", default=None
)


def is_stub_authorization(value: Optional[str]) -> bool:
    """True for local stub login tokens (not valid on Databricks)."""
    return bool(value and _STUB_AUTH_RE.match(value.strip()))


def _header_value(headers: Mapping[str, Any], name: str) -> Optional[str]:
    key = name.lower()
    for header_name, value in headers.items():
        if str(header_name).lower() == key:
            if isinstance(value, (list, tuple)):
                return str(value[0]).strip() if value else None
            return str(value).strip() if value is not None else None
    return None


def extract_forwarded_databricks_token(headers: Mapping[str, Any]) -> Optional[str]:
    """Read user OAuth from Databricks Apps gateway / proxy headers.

    Used by API middleware before ``set_request_databricks_token``.
    """
    for name in _FORWARDED_TOKEN_HEADERS:
        token = _header_value(headers, name)
        if token:
            return token

    authorization = _header_value(headers, "authorization")
    if authorization and not is_stub_authorization(authorization):
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
            return token or None
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
            "For local dev run `az login`. "
            "On Databricks Apps, ensure middleware sets the user OAuth token."
        ) from exc


def resolve_access_token(*, source_name: str = "") -> str:
    """Resolve a SQL warehouse access token.

    1. Request-scoped user OAuth (Databricks Apps → API middleware)
    2. Else DefaultAzureCredential (local ``az login``)
    """
    label = source_name or "source"

    scoped = get_request_databricks_token()
    if scoped:
        logger.debug("databricks_token_from_request_scope", extra={"source": label})
        return scoped

    logger.debug("databricks_token_via_azure_credential", extra={"source": label})
    return get_azure_databricks_token()
