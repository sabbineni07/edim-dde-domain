"""Foundry SP → API key → DefaultAzureCredential resolution and provider wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from edim_dde_domain.config import DomainSettings, clear_settings_cache
from edim_dde_domain.llm.foundry import (
    AZURE_FOUNDRY_AAD_SCOPE,
    FoundryLLMNotConfiguredError,
    FoundryLLMProvider,
    _openai_v1_base_url,
    clear_foundry_llm_provider_cache,
    foundry_auth_mode,
    foundry_auth_provider,
    foundry_token_provider,
    get_foundry_access_token,
)


def _clear() -> None:
    clear_settings_cache()
    clear_foundry_llm_provider_cache()


def _settings(**overrides) -> DomainSettings:
    """Build settings that ignore process/.env SP and API-key vars unless set."""
    base = dict(
        edim_foundry_tenant_id="",
        edim_foundry_client_id="",
        edim_foundry_client_secret="",
        azure_tenant_id="",
        azure_client_id="",
        azure_client_secret="",
        edim_foundry_api_key="",
        azure_openai_api_key="",
        azure_openai_endpoint_key="",
        azure_openai_endpoint="https://global.example.com",
        azure_openai_deployment_name="gpt-global",
    )
    base.update(overrides)
    return DomainSettings(**base)


# ---------------------------------------------------------------------------
# SP credential resolution
# ---------------------------------------------------------------------------


def test_foundry_sp_prefers_edim_foundry_vars():
    _clear()
    s = _settings(
        edim_foundry_tenant_id="ft",
        edim_foundry_client_id="fc",
        edim_foundry_client_secret="fs",
        azure_tenant_id="at",
        azure_client_id="ac",
        azure_client_secret="as",
    )
    assert s.foundry_sp_credentials() == ("ft", "fc", "fs")


def test_foundry_sp_falls_back_to_legacy_azure_client():
    _clear()
    s = _settings(
        azure_tenant_id="at",
        azure_client_id="ac",
        azure_client_secret="as",
    )
    assert s.foundry_sp_credentials() == ("at", "ac", "as")


def test_foundry_sp_can_mix_client_with_shared_tenant():
    _clear()
    s = _settings(
        edim_foundry_client_id="fc",
        edim_foundry_client_secret="fs",
        azure_tenant_id="shared-tenant",
    )
    assert s.foundry_sp_credentials() == ("shared-tenant", "fc", "fs")


def test_incomplete_sp_does_not_count_as_configured():
    _clear()
    # Missing secret → not SP; falls through.
    s = _settings(
        edim_foundry_tenant_id="ft",
        edim_foundry_client_id="fc",
        edim_foundry_client_secret="",
        azure_openai_endpoint_key="k",
    )
    assert foundry_auth_mode(s) == "api_key"


# ---------------------------------------------------------------------------
# API key preference
# ---------------------------------------------------------------------------


def test_foundry_api_key_preference_order():
    _clear()
    assert (
        _settings(
            edim_foundry_api_key="edim-key",
            azure_openai_api_key="openai-key",
            azure_openai_endpoint_key="endpoint-key",
        ).foundry_api_key()
        == "edim-key"
    )
    assert (
        _settings(
            azure_openai_api_key="openai-key",
            azure_openai_endpoint_key="endpoint-key",
        ).foundry_api_key()
        == "openai-key"
    )
    assert (
        _settings(azure_openai_endpoint_key="endpoint-key").foundry_api_key()
        == "endpoint-key"
    )
    assert _settings().foundry_api_key() == ""


def test_foundry_api_key_ignores_whitespace():
    _clear()
    assert _settings(edim_foundry_api_key="   ").foundry_api_key() == ""
    assert (
        _settings(
            edim_foundry_api_key="  ",
            azure_openai_api_key=" real-key ",
        ).foundry_api_key()
        == "real-key"
    )


# ---------------------------------------------------------------------------
# Auth mode order: SP → key → DAC
# ---------------------------------------------------------------------------


def test_foundry_auth_mode_sp_beats_api_key():
    _clear()
    s = _settings(
        edim_foundry_tenant_id="ft",
        edim_foundry_client_id="fc",
        edim_foundry_client_secret="fs",
        edim_foundry_api_key="should-not-win",
    )
    assert foundry_auth_mode(s) == "sp"


def test_foundry_auth_mode_legacy_sp_beats_api_key():
    _clear()
    s = _settings(
        azure_tenant_id="at",
        azure_client_id="ac",
        azure_client_secret="as",
        azure_openai_endpoint_key="key-loses",
    )
    assert foundry_auth_mode(s) == "sp"


def test_foundry_auth_mode_api_key_before_dac():
    _clear()
    s = _settings(azure_openai_endpoint_key="k")
    assert foundry_auth_mode(s) == "api_key"
    assert foundry_auth_provider(s)() == "k"


def test_foundry_auth_mode_dac_when_no_sp_or_key():
    _clear()
    assert foundry_auth_mode(_settings()) == "default_azure_credential"


def test_foundry_token_provider_alias_returns_api_key():
    _clear()
    s = _settings(edim_foundry_api_key="alias-key")
    assert foundry_token_provider(s)() == "alias-key"


# ---------------------------------------------------------------------------
# AAD token minting (mocked)
# ---------------------------------------------------------------------------


def test_get_foundry_access_token_uses_sp_credential():
    _clear()
    s = _settings(
        edim_foundry_tenant_id="ft",
        edim_foundry_client_id="fc",
        edim_foundry_client_secret="fs",
    )
    fake_cred = MagicMock()
    fake_cred.get_token.return_value = SimpleNamespace(token="  sp-token  ")

    with patch(
        "edim_dde_domain.llm.foundry._azure_sp_or_dac_credential",
        return_value=fake_cred,
    ):
        assert get_foundry_access_token(s) == "sp-token"

    fake_cred.get_token.assert_called_once_with(AZURE_FOUNDRY_AAD_SCOPE)


def test_get_foundry_access_token_empty_raises():
    _clear()
    fake_cred = MagicMock()
    fake_cred.get_token.return_value = SimpleNamespace(token="  ")
    with patch(
        "edim_dde_domain.llm.foundry._azure_sp_or_dac_credential",
        return_value=fake_cred,
    ):
        with pytest.raises(FoundryLLMNotConfiguredError, match="empty"):
            get_foundry_access_token(_settings())


def test_get_foundry_access_token_wraps_credential_errors():
    _clear()
    fake_cred = MagicMock()
    fake_cred.get_token.side_effect = RuntimeError("no az")
    with patch(
        "edim_dde_domain.llm.foundry._azure_sp_or_dac_credential",
        return_value=fake_cred,
    ):
        with pytest.raises(FoundryLLMNotConfiguredError, match="Failed to obtain"):
            get_foundry_access_token(_settings())


def test_sp_auth_provider_mints_token_via_get_foundry_access_token():
    _clear()
    s = _settings(
        edim_foundry_tenant_id="ft",
        edim_foundry_client_id="fc",
        edim_foundry_client_secret="fs",
    )
    with patch(
        "edim_dde_domain.llm.foundry.get_foundry_access_token",
        return_value="minted",
    ) as mint:
        assert foundry_auth_provider(s)() == "minted"
        mint.assert_called_once_with(s)


def test_dac_auth_provider_mints_token_via_get_foundry_access_token():
    _clear()
    s = _settings()
    assert foundry_auth_mode(s) == "default_azure_credential"
    with patch(
        "edim_dde_domain.llm.foundry.get_foundry_access_token",
        return_value="dac-tok",
    ) as mint:
        assert foundry_auth_provider(s)() == "dac-tok"
        mint.assert_called_once_with(s)


def test_azure_sp_credential_constructs_client_secret():
    _clear()
    from edim_dde_domain.llm import foundry as foundry_mod

    s = _settings(
        edim_foundry_tenant_id="ft",
        edim_foundry_client_id="fc",
        edim_foundry_client_secret="fs",
    )
    with patch("azure.identity.ClientSecretCredential") as ctor:
        foundry_mod._azure_sp_or_dac_credential(s)
    ctor.assert_called_once_with(
        tenant_id="ft", client_id="fc", client_secret="fs"
    )


def test_azure_dac_credential_when_no_sp():
    _clear()
    from edim_dde_domain.llm import foundry as foundry_mod

    with patch("azure.identity.DefaultAzureCredential") as ctor:
        foundry_mod._azure_sp_or_dac_credential(_settings())
    ctor.assert_called_once_with()


# ---------------------------------------------------------------------------
# FoundryLLMProvider construction + invoke with API key
# ---------------------------------------------------------------------------


def test_provider_requires_endpoint():
    _clear()
    with pytest.raises(FoundryLLMNotConfiguredError, match="AZURE_OPENAI_ENDPOINT"):
        FoundryLLMProvider(settings=_settings(azure_openai_endpoint=""))


def test_provider_auth_mode_api_key_and_passes_key_to_openai():
    _clear()
    s = _settings(azure_openai_endpoint_key="live-key")
    provider = FoundryLLMProvider(settings=s)
    assert provider._auth_mode == "api_key"

    fake_choice = SimpleNamespace(message=SimpleNamespace(content="ok"))
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[fake_choice]
    )

    with patch("openai.OpenAI", return_value=fake_client) as ctor:
        text = provider.invoke([("human", "hi")])

    assert text == "ok"
    assert ctor.call_args.kwargs["api_key"] == "live-key"
    assert ctor.call_args.kwargs["base_url"] == (
        "https://global.example.com/openai/v1"
    )


def test_provider_auth_mode_sp():
    _clear()
    s = _settings(
        edim_foundry_tenant_id="ft",
        edim_foundry_client_id="fc",
        edim_foundry_client_secret="fs",
        azure_openai_endpoint_key="ignored",
    )
    provider = FoundryLLMProvider(settings=s)
    assert provider._auth_mode == "sp"


def test_provider_auth_mode_dac():
    _clear()
    provider = FoundryLLMProvider(settings=_settings())
    assert provider._auth_mode == "default_azure_credential"


def test_provider_invoke_with_sp_token_provider():
    _clear()
    s = _settings(
        edim_foundry_tenant_id="ft",
        edim_foundry_client_id="fc",
        edim_foundry_client_secret="fs",
    )
    provider = FoundryLLMProvider(settings=s)
    fake_choice = SimpleNamespace(message=SimpleNamespace(content="sp-ok"))
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[fake_choice]
    )

    with (
        patch(
            "edim_dde_domain.llm.foundry.get_foundry_access_token",
            return_value="aad-token",
        ),
        patch("openai.OpenAI", return_value=fake_client) as ctor,
    ):
        assert provider.invoke([("human", "x")]) == "sp-ok"

    assert ctor.call_args.kwargs["api_key"] == "aad-token"


def test_provider_invoke_empty_choices_returns_empty_string():
    _clear()
    provider = FoundryLLMProvider(settings=_settings(edim_foundry_api_key="k"))
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = SimpleNamespace(choices=[])

    with patch("openai.OpenAI", return_value=fake_client):
        assert provider.invoke([("human", "x")]) == ""


def test_provider_explanation_chain_default_temperature():
    _clear()
    provider = FoundryLLMProvider(settings=_settings(edim_foundry_api_key="k"))
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="e"))]
    )

    with patch("openai.OpenAI", return_value=fake_client):
        provider.invoke([("human", "x")], config={"chain": "explanation"})

    assert fake_client.chat.completions.create.call_args.kwargs["temperature"] == 0.2


# ---------------------------------------------------------------------------
# URL normalization
# ---------------------------------------------------------------------------


def test_openai_v1_base_url_strips_responses_and_avoids_double_append():
    host = "https://example.openai.azure.com"
    assert _openai_v1_base_url(host) == f"{host}/openai/v1"
    assert _openai_v1_base_url(f"{host}/openai/v1") == f"{host}/openai/v1"
    assert _openai_v1_base_url(f"{host}/openai") == f"{host}/openai/v1"
    assert _openai_v1_base_url(f"{host}/openai/v1/responses") == f"{host}/openai/v1"
    assert _openai_v1_base_url(f"{host}/responses") == f"{host}/openai/v1"
    assert _openai_v1_base_url(f"{host}/openai/v1/openai/v1") == f"{host}/openai/v1"
    assert _openai_v1_base_url("") == ""
    assert _openai_v1_base_url("   ") == ""
