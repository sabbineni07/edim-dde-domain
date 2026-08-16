"""Foundry SP env resolution prefers EDIM_FOUNDRY_* over legacy AZURE_CLIENT_*."""

from __future__ import annotations

from edim_dde_domain.config import DomainSettings, clear_settings_cache
from edim_dde_domain.llm.foundry import _openai_v1_base_url


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


def test_openai_v1_base_url_strips_responses_and_avoids_double_append():
    host = "https://example.openai.azure.com"
    assert _openai_v1_base_url(host) == f"{host}/openai/v1"
    assert _openai_v1_base_url(f"{host}/openai/v1") == f"{host}/openai/v1"
    assert _openai_v1_base_url(f"{host}/openai") == f"{host}/openai/v1"
    assert _openai_v1_base_url(f"{host}/openai/v1/responses") == f"{host}/openai/v1"
    assert _openai_v1_base_url(f"{host}/responses") == f"{host}/openai/v1"
    assert _openai_v1_base_url(f"{host}/openai/v1/openai/v1") == f"{host}/openai/v1"
