"""Azure AI Foundry (OpenAI v1) LLM provider for edim-dde-ai ``llm_chain``.

Business purpose
----------------
Adapter that hosts call via ``set_llm_provider(get_foundry_llm_provider())``.
Uses Azure AD tokens (not API keys) against Foundry's OpenAI-compatible
``/openai/v1`` surface. Keeps Foundry SP on ``EDIM_FOUNDRY_*`` so SQL's
``DefaultAzureCredential`` is not polluted by ``AZURE_CLIENT_*``.

Auth order
----------
1. ``EDIM_FOUNDRY_TENANT_ID`` + ``EDIM_FOUNDRY_CLIENT_ID`` +
   ``EDIM_FOUNDRY_CLIENT_SECRET`` → ``ClientSecretCredential``
   (prod: inject from Key Vault into these env names — not ``AZURE_CLIENT_*``)
2. Legacy fallback: ``AZURE_TENANT_ID`` / ``AZURE_CLIENT_ID`` / ``AZURE_CLIENT_SECRET``
   (deprecated; pollutes ``DefaultAzureCredential`` used for SQL)
3. Else ``DefaultAzureCredential`` (local ``az login`` / Managed Identity)

Scope: ``https://ai.azure.com/.default``

Public API
----------
* ``AZURE_FOUNDRY_AAD_SCOPE``
* ``FoundryLLMNotConfiguredError``
* ``get_foundry_access_token`` / ``foundry_token_provider``
* ``FoundryLLMProvider`` — ``invoke(messages, config=...)``
* ``get_foundry_llm_provider`` / ``clear_foundry_llm_provider_cache``
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Callable, Optional

from edim_dde_domain.config import DomainSettings, get_settings
from edim_dde_domain.errors import DomainToolError

logger = logging.getLogger(__name__)

AZURE_FOUNDRY_AAD_SCOPE = "https://ai.azure.com/.default"
_legacy_sp_warned = False


class FoundryLLMNotConfiguredError(DomainToolError):
    """Foundry endpoint / credentials missing or token fetch failed."""


def _openai_v1_base_url(endpoint: str) -> str:
    """Normalize a Foundry/OpenAI endpoint to an ``.../openai/v1`` base URL.

    Accepts common env-value shapes so callers do not double-append paths:

    * bare resource host
    * already ends with ``/openai`` or ``/openai/v1``
    * accidentally includes ``/responses``, ``/chat/completions``, etc.

    Args:
        endpoint: Raw ``EDIM_FOUNDRY_ENDPOINT`` / Azure OpenAI-style URL.

    Returns:
        Base URL ending in ``/openai/v1``, or ``\"\"`` when empty.
    """
    base = (endpoint or "").strip().rstrip("/")
    if not base:
        return ""
    # Strip operation suffixes that belong on the client path, not the base.
    for suffix in (
        "/responses",
        "/chat/completions",
        "/completions",
        "/embeddings",
    ):
        if base.lower().endswith(suffix):
            base = base[: -len(suffix)].rstrip("/")
            break
    # Collapse accidental duplicated /openai/v1 segments.
    lowered = base.lower()
    marker = "/openai/v1"
    if marker in lowered:
        idx = lowered.index(marker)
        base = base[: idx + len(marker)]
        return base.rstrip("/")
    if base.lower().endswith("/openai"):
        return f"{base}/v1"
    return f"{base}/openai/v1"


def _azure_credential(settings: DomainSettings):
    global _legacy_sp_warned
    tenant_id, client_id, client_secret = settings.foundry_sp_credentials()
    try:
        if tenant_id and client_id and client_secret:
            from azure.identity import ClientSecretCredential

            dedicated = bool(
                (settings.edim_foundry_client_id or "").strip()
                and (settings.edim_foundry_client_secret or "").strip()
            )
            if not dedicated and not _legacy_sp_warned:
                _legacy_sp_warned = True
                logger.warning(
                    "Foundry auth is using legacy AZURE_CLIENT_ID/SECRET "
                    "(and/or AZURE_TENANT_ID). Prefer EDIM_FOUNDRY_CLIENT_ID / "
                    "EDIM_FOUNDRY_CLIENT_SECRET / EDIM_FOUNDRY_TENANT_ID so SQL "
                    "DefaultAzureCredential is not tied to the Foundry SP. "
                    "See docs/platform/access-and-permissions.md"
                )
            return ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )
        from azure.identity import DefaultAzureCredential

        return DefaultAzureCredential()
    except ImportError as exc:
        raise FoundryLLMNotConfiguredError(
            "azure-identity is required for Foundry auth. "
            "Install with: pip install 'edim-dde-domain[azure]'"
        ) from exc


def get_foundry_access_token(settings: Optional[DomainSettings] = None) -> str:
    """Mint an Azure AD token for Foundry (SP secret or az login).

    Args:
        settings: Optional settings; defaults to ``get_settings()``.

    Returns:
        Non-empty access token string.

    Raises:
        FoundryLLMNotConfiguredError: Missing azure-identity, empty token, or
            credential failure.
    """
    cfg = settings or get_settings()
    try:
        token = _azure_credential(cfg).get_token(AZURE_FOUNDRY_AAD_SCOPE)
        access = (token.token or "").strip()
        if not access:
            raise FoundryLLMNotConfiguredError("Azure credential returned an empty Foundry token")
        return access
    except FoundryLLMNotConfiguredError:
        raise
    except Exception as exc:
        raise FoundryLLMNotConfiguredError(
            "Failed to obtain Foundry token via Azure credential "
            f"({type(exc).__name__}: {exc}). "
            "For local dev run `az login`. "
            "For prod set EDIM_FOUNDRY_TENANT_ID / EDIM_FOUNDRY_CLIENT_ID / "
            "EDIM_FOUNDRY_CLIENT_SECRET "
            "(secrets typically loaded from Azure Key Vault into the environment)."
        ) from exc


def foundry_token_provider(
    settings: Optional[DomainSettings] = None,
) -> Callable[[], str]:
    """Return a zero-arg callable that mints a fresh Foundry access token.

    Args:
        settings: Settings snapshot closed over by the provider.

    Returns:
        Callable suitable as OpenAI ``api_key`` (refreshed per invoke).
    """
    cfg = settings or get_settings()

    def _provider() -> str:
        return get_foundry_access_token(cfg)

    return _provider


class FoundryLLMProvider:
    """``LLMProvider`` adapter: Foundry chat completions via OpenAI v1 API.

    Raises ``FoundryLLMNotConfiguredError`` at construction if
    ``AZURE_OPENAI_ENDPOINT`` is unset. Deployment defaults to ``gpt-4o``.
    """

    def __init__(self, settings: Optional[DomainSettings] = None) -> None:
        self._settings = settings or get_settings()
        endpoint = (self._settings.azure_openai_endpoint or "").strip()
        if not endpoint:
            raise FoundryLLMNotConfiguredError(
                "Azure AI Foundry is not configured. Set AZURE_OPENAI_ENDPOINT "
                "and authenticate with EDIM_FOUNDRY_TENANT_ID/CLIENT_ID/SECRET "
                "(Key Vault → env in prod) or `az login` locally."
            )
        self._base_url = _openai_v1_base_url(endpoint)
        self._model = (
            (self._settings.azure_openai_deployment_name or "").strip() or "gpt-4o"
        )
        self._token_provider = foundry_token_provider(self._settings)

    def invoke(
        self,
        messages: list[tuple[str, str]],
        *,
        config: dict[str, Any] | None = None,
    ) -> str:
        """Run a chat completion and return assistant text.

        Args:
            messages: ``(role, content)`` pairs (``system`` / ``human`` / ``ai``).
            config: Optional knobs; ``chain == "explanation"`` raises temperature
                to ``0.2`` (default ``0.0``).

        Returns:
            Stripped assistant message content, or ``""`` if empty.

        Raises:
            FoundryLLMNotConfiguredError: ``openai`` package missing.
        """
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise FoundryLLMNotConfiguredError(
                "openai is required for Foundry LLM. "
                "Install with: pip install 'edim-dde-domain[llm]'"
            ) from exc

        temperature = 0.0
        if config and config.get("chain") == "explanation":
            temperature = 0.2

        client = OpenAI(
            base_url=self._base_url,
            api_key=self._token_provider(),
        )
        normalized = []
        for role, content in messages:
            r = role.lower().strip()
            if r in ("system",):
                normalized.append({"role": "system", "content": content})
            elif r in ("assistant", "ai"):
                normalized.append({"role": "assistant", "content": content})
            else:
                normalized.append({"role": "user", "content": content})

        logger.debug(
            "foundry_chat_invoke",
            extra={"model": self._model, "base_url": self._base_url, "n_messages": len(normalized)},
        )
        resp = client.chat.completions.create(
            model=self._model,
            messages=normalized,
            temperature=temperature,
        )
        choice = (resp.choices or [None])[0]
        if choice is None or choice.message is None:
            return ""
        return (choice.message.content or "").strip()


@lru_cache(maxsize=1)
def get_foundry_llm_provider() -> FoundryLLMProvider:
    """Process-wide Foundry provider (uses cached DomainSettings).

    Returns:
        Singleton ``FoundryLLMProvider``.
    """
    return FoundryLLMProvider(get_settings())


def clear_foundry_llm_provider_cache() -> None:
    """Drop the cached provider (tests / after settings change)."""
    get_foundry_llm_provider.cache_clear()
