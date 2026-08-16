"""Azure AI Foundry (OpenAI v1) LLM provider for edim-dde-ai ``llm_chain``.

Business purpose
----------------
Adapter that hosts call via ``set_llm_provider(get_foundry_llm_provider())``.
Talks to Foundry's OpenAI-compatible ``/openai/v1`` surface. Keeps Foundry SP
on ``EDIM_FOUNDRY_*`` so SQL's ``DefaultAzureCredential`` is not polluted by
``AZURE_CLIENT_*``.

Auth order
----------
1. Foundry SP — ``EDIM_FOUNDRY_TENANT_ID`` + ``CLIENT_ID`` + ``CLIENT_SECRET``
   (legacy ``AZURE_TENANT_ID`` / ``AZURE_CLIENT_*`` fallback; prod often via KV)
2. API key — ``EDIM_FOUNDRY_API_KEY``, else ``AZURE_OPENAI_API_KEY``, else
   ``AZURE_OPENAI_ENDPOINT_KEY`` (skips ``az login`` when a key is present)
3. ``DefaultAzureCredential`` — local ``az login`` / Managed Identity

AAD scope (SP / DAC only): ``https://ai.azure.com/.default``

Public API
----------
* ``AZURE_FOUNDRY_AAD_SCOPE``
* ``FoundryLLMNotConfiguredError``
* ``get_foundry_access_token`` / ``foundry_token_provider`` / ``foundry_auth_provider``
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
_api_key_warned = False


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


def _foundry_sp_configured(settings: DomainSettings) -> bool:
    tenant_id, client_id, client_secret = settings.foundry_sp_credentials()
    return bool(tenant_id and client_id and client_secret)


def _azure_sp_or_dac_credential(settings: DomainSettings):
    """Build ClientSecretCredential (SP) or DefaultAzureCredential (no key path)."""
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
            "azure-identity is required for Foundry AAD auth. "
            "Install with: pip install 'edim-dde-domain[azure]', "
            "or set EDIM_FOUNDRY_API_KEY / AZURE_OPENAI_API_KEY for key auth."
        ) from exc


def get_foundry_access_token(settings: Optional[DomainSettings] = None) -> str:
    """Mint an Azure AD token for Foundry (SP or DefaultAzureCredential).

    Does **not** return an API key — use ``foundry_auth_provider`` for the
    full SP → key → DAC resolution used by ``FoundryLLMProvider``.

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
        token = _azure_sp_or_dac_credential(cfg).get_token(AZURE_FOUNDRY_AAD_SCOPE)
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
            "For local dev run `az login`, or set EDIM_FOUNDRY_API_KEY. "
            "For prod set EDIM_FOUNDRY_TENANT_ID / EDIM_FOUNDRY_CLIENT_ID / "
            "EDIM_FOUNDRY_CLIENT_SECRET "
            "(secrets typically loaded from Azure Key Vault into the environment)."
        ) from exc


def foundry_auth_mode(settings: Optional[DomainSettings] = None) -> str:
    """Return which Foundry auth plane would be selected (no network I/O).

    Returns:
        ``\"sp\"`` | ``\"api_key\"`` | ``\"default_azure_credential\"``.
    """
    cfg = settings or get_settings()
    if _foundry_sp_configured(cfg):
        return "sp"
    if cfg.foundry_api_key():
        return "api_key"
    return "default_azure_credential"


def foundry_auth_provider(
    settings: Optional[DomainSettings] = None,
) -> Callable[[], str]:
    """Return a zero-arg callable that yields the OpenAI client ``api_key``.

    Resolution order: Foundry SP (AAD token) → API key → DefaultAzureCredential
    (AAD token via ``az login`` / MI).

    Args:
        settings: Settings snapshot closed over by the provider.

    Returns:
        Callable suitable as OpenAI ``api_key`` (refreshed per invoke for AAD).
    """
    global _api_key_warned
    cfg = settings or get_settings()
    mode = foundry_auth_mode(cfg)

    if mode == "sp":

        def _sp_provider() -> str:
            return get_foundry_access_token(cfg)

        return _sp_provider

    if mode == "api_key":
        key = cfg.foundry_api_key()
        if not _api_key_warned:
            _api_key_warned = True
            logger.info(
                "Foundry auth using API key "
                "(EDIM_FOUNDRY_API_KEY / AZURE_OPENAI_API_KEY / "
                "AZURE_OPENAI_ENDPOINT_KEY). Prefer EDIM_FOUNDRY_* SP or "
                "`az login` in shared environments."
            )

        def _key_provider() -> str:
            return key

        return _key_provider

    def _dac_provider() -> str:
        return get_foundry_access_token(cfg)

    return _dac_provider


def foundry_token_provider(
    settings: Optional[DomainSettings] = None,
) -> Callable[[], str]:
    """Alias of ``foundry_auth_provider`` (historical name; may return an API key)."""
    return foundry_auth_provider(settings)


class FoundryLLMProvider:
    """``LLMProvider`` adapter: Foundry chat completions via OpenAI v1 API.

    Raises ``FoundryLLMNotConfiguredError`` at construction if
    ``AZURE_OPENAI_ENDPOINT`` is unset. Deployment defaults to ``gpt-4o``.
    Auth: SP → API key → DefaultAzureCredential (see module docstring).
    """

    def __init__(self, settings: Optional[DomainSettings] = None) -> None:
        self._settings = settings or get_settings()
        endpoint = (self._settings.azure_openai_endpoint or "").strip()
        if not endpoint:
            raise FoundryLLMNotConfiguredError(
                "Azure AI Foundry is not configured. Set AZURE_OPENAI_ENDPOINT "
                "and authenticate with EDIM_FOUNDRY_TENANT_ID/CLIENT_ID/SECRET "
                "(Key Vault → env in prod), EDIM_FOUNDRY_API_KEY / "
                "AZURE_OPENAI_API_KEY, or `az login` locally."
            )
        self._base_url = _openai_v1_base_url(endpoint)
        self._model = (
            (self._settings.azure_openai_deployment_name or "").strip() or "gpt-4o"
        )
        self._auth_mode = foundry_auth_mode(self._settings)
        self._token_provider = foundry_auth_provider(self._settings)

    def invoke(
        self,
        messages: list[tuple[str, str]],
        *,
        config: dict[str, Any] | None = None,
    ) -> str:
        """Run a chat completion and return assistant text.

        Args:
            messages: ``(role, content)`` pairs (``system`` / ``human`` / ``ai``).
            config: Optional knobs:
                * ``temperature`` — explicit override (bindings or node); else
                  ``chain == "explanation"`` → ``0.2``, default ``0.0``
                * ``top_p`` / ``max_tokens`` — optional chat-completion knobs
                  (``max_tokens`` is sent as ``max_completion_tokens``)
                * ``endpoint`` / ``deployment`` — Phase 1 agent ``bindings.llm``
                  overrides injected by GraphBuilder (omit → process globals)
                * ``top_k`` — accepted on config for forward-compat; not sent to
                  OpenAI chat completions (use ``top_p`` for nucleus sampling)

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

        # Phase 1 agent bindings: optional per-invoke endpoint/deployment/knobs.
        endpoint_override = ""
        model = self._model
        top_p: float | None = None
        max_tokens: int | None = None
        if config:
            endpoint_override = str(config.get("endpoint") or "").strip()
            deployment_override = str(config.get("deployment") or "").strip()
            if deployment_override:
                model = deployment_override
            if config.get("temperature") is not None:
                try:
                    temperature = float(config["temperature"])
                except (TypeError, ValueError):
                    pass
            if config.get("top_p") is not None:
                try:
                    top_p = float(config["top_p"])
                except (TypeError, ValueError):
                    top_p = None
            if config.get("max_tokens") is not None:
                try:
                    max_tokens = int(config["max_tokens"])
                except (TypeError, ValueError):
                    max_tokens = None
        base_url = (
            _openai_v1_base_url(endpoint_override)
            if endpoint_override
            else self._base_url
        )

        client = OpenAI(
            base_url=base_url,
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

        create_kwargs: dict[str, Any] = {
            "model": model,
            "messages": normalized,
            "temperature": temperature,
        }
        if top_p is not None:
            create_kwargs["top_p"] = top_p
        if max_tokens is not None:
            # Newer Foundry/OpenAI models (e.g. gpt-5.x) require max_completion_tokens.
            create_kwargs["max_completion_tokens"] = max_tokens

        logger.debug(
            "foundry_chat_invoke",
            extra={
                "model": model,
                "base_url": base_url,
                "n_messages": len(normalized),
                "auth_mode": self._auth_mode,
            },
        )
        resp = client.chat.completions.create(**create_kwargs)
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
