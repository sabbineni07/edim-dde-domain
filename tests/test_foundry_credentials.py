"""Foundry SP / API key / DAC auth resolution."""

from __future__ import annotations

from edim_dde_domain.config import DomainSettings, clear_settings_cache
from edim_dde_domain.llm.foundry import (
    _openai_v1_base_url,
    clear_foundry_llm_provider_cache,
    foundry_auth_mode,
    foundry_auth_provider,
)


def test_foundry_sp_prefers_edim_foundry_vars():
    clear_settings_cache()
    s = DomainSettings(
        edim_foundry_tenant_id="ft",
        edim_foundry_client_id="fc",
        edim_foundry_client_secret="fs",
        azure_tenant_id="at",
        azure_client_id="ac",
        azure_client_secret="as",
    )
    assert s.foundry_sp_credentials() == ("ft", "fc", "fs")


def test_foundry_sp_falls_back_to_legacy_azure_client():
    clear_settings_cache()
    s = DomainSettings(
        azure_tenant_id="at",
        azure_client_id="ac",
        azure_client_secret="as",
    )
    assert s.foundry_sp_credentials() == ("at", "ac", "as")


def test_foundry_sp_can_mix_client_with_shared_tenant():
    clear_settings_cache()
    s = DomainSettings(
        edim_foundry_client_id="fc",
        edim_foundry_client_secret="fs",
        azure_tenant_id="shared-tenant",
    )
    assert s.foundry_sp_credentials() == ("shared-tenant", "fc", "fs")


def test_foundry_api_key_preference_order():
    clear_settings_cache()
    s = DomainSettings(
        edim_foundry_api_key="edim-key",
        azure_openai_api_key="openai-key",
        azure_openai_endpoint_key="endpoint-key",
    )
    assert s.foundry_api_key() == "edim-key"
    s2 = DomainSettings(
        edim_foundry_api_key="",
        azure_openai_api_key="openai-key",
        azure_openai_endpoint_key="endpoint-key",
    )
    assert s2.foundry_api_key() == "openai-key"
    s3 = DomainSettings(
        edim_foundry_api_key="",
        azure_openai_api_key="",
        azure_openai_endpoint_key="endpoint-key",
    )
    assert s3.foundry_api_key() == "endpoint-key"
    s4 = DomainSettings(
        edim_foundry_api_key="",
        azure_openai_api_key="",
        azure_openai_endpoint_key="",
    )
    assert s4.foundry_api_key() == ""


def test_foundry_auth_mode_sp_beats_api_key():
    clear_settings_cache()
    clear_foundry_llm_provider_cache()
    s = DomainSettings(
        edim_foundry_tenant_id="ft",
        edim_foundry_client_id="fc",
        edim_foundry_client_secret="fs",
        edim_foundry_api_key="should-not-win",
        azure_openai_api_key="",
        azure_openai_endpoint_key="",
    )
    assert foundry_auth_mode(s) == "sp"


def test_foundry_auth_mode_api_key_before_dac():
    clear_settings_cache()
    clear_foundry_llm_provider_cache()
    s = DomainSettings(
        edim_foundry_tenant_id="",
        edim_foundry_client_id="",
        edim_foundry_client_secret="",
        azure_tenant_id="",
        azure_client_id="",
        azure_client_secret="",
        azure_openai_endpoint_key="k",
    )
    assert foundry_auth_mode(s) == "api_key"
    assert foundry_auth_provider(s)() == "k"


def test_foundry_auth_mode_dac_when_no_sp_or_key():
    clear_settings_cache()
    clear_foundry_llm_provider_cache()
    s = DomainSettings(
        edim_foundry_tenant_id="",
        edim_foundry_client_id="",
        edim_foundry_client_secret="",
        azure_tenant_id="",
        azure_client_id="",
        azure_client_secret="",
        edim_foundry_api_key="",
        azure_openai_api_key="",
        azure_openai_endpoint_key="",
    )
    assert foundry_auth_mode(s) == "default_azure_credential"


def test_openai_v1_base_url_strips_responses_and_avoids_double_append():
    host = "https://example.openai.azure.com"
    assert _openai_v1_base_url(host) == f"{host}/openai/v1"
    assert _openai_v1_base_url(f"{host}/openai/v1") == f"{host}/openai/v1"
    assert _openai_v1_base_url(f"{host}/openai") == f"{host}/openai/v1"
    assert _openai_v1_base_url(f"{host}/openai/v1/responses") == f"{host}/openai/v1"
    assert _openai_v1_base_url(f"{host}/responses") == f"{host}/openai/v1"
    assert _openai_v1_base_url(f"{host}/openai/v1/openai/v1") == f"{host}/openai/v1"
