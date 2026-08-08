"""Azure AI Foundry (OpenAI v1) LLM provider for edim-dde-ai ``llm_chain``.

Auth:
1. ``EDIM_FOUNDRY_TENANT_ID`` + ``EDIM_FOUNDRY_CLIENT_ID`` +
   ``EDIM_FOUNDRY_CLIENT_SECRET`` → ``ClientSecretCredential``
   (prod: inject from Key Vault into these env names — not ``AZURE_CLIENT_*``)
2. Legacy fallback: ``AZURE_TENANT_ID`` / ``AZURE_CLIENT_ID`` / ``AZURE_CLIENT_SECRET``
   (deprecated; pollutes ``DefaultAzureCredential`` used for SQL)
3. Else ``DefaultAzureCredential`` (local ``az login`` / Managed Identity)

Scope: ``https://ai.azure.com/.default``
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
    base = (endpoint or "").strip().rstrip("/")
    if not base:
        return ""
    if base.endswith("/openai/v1"):
        return base
    if base.endswith("/openai"):
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
    """Mint an Azure AD token for Foundry (SP secret or az login)."""
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
    cfg = settings or get_settings()

    def _provider() -> str:
        return get_foundry_access_token(cfg)

    return _provider


class FoundryLLMProvider:
    """``LLMProvider`` adapter: Foundry chat completions via OpenAI v1 API."""

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
    """Process-wide Foundry provider (uses cached DomainSettings)."""
    return FoundryLLMProvider(get_settings())


def clear_foundry_llm_provider_cache() -> None:
    get_foundry_llm_provider.cache_clear()
