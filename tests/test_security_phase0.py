"""PII redaction + Key Vault map parsing."""

from __future__ import annotations

from edim_dde_domain.security.keyvault import parse_secret_map
from edim_dde_domain.security.pii import redact_text, redact_value


def test_redact_ssn_and_member():
    text = "ssn 123-45-6789 and Member ID: AB12-99"
    out = redact_text(text)
    assert "123-45-6789" not in out
    assert "[REDACTED:ssn]" in out
    assert "[REDACTED:member_id]" in out


def test_redact_credit_card_grouped():
    text = "card 4111-1111-1111-1111 on file"
    out = redact_text(text)
    assert "4111-1111-1111-1111" not in out
    assert "[REDACTED:credit_card]" in out


def test_redact_does_not_eat_short_telemetry_ids():
    text = "cluster_id=c123 job_id=456"
    assert redact_text(text) == text


def test_redact_nested():
    payload = {"note": "account number 998877", "n": 1}
    out = redact_value(payload)
    assert "[REDACTED:account_number]" in out["note"]
    assert out["n"] == 1


def test_parse_secret_map_default():
    m = parse_secret_map(None)
    assert m["EDIM_FOUNDRY_CLIENT_ID"] == "azure-client-id"
    assert m["EDIM_FOUNDRY_CLIENT_SECRET"] == "azure-client-secret"
    assert m["EDIM_FOUNDRY_TENANT_ID"] == "azure-tenant-id"
    assert m["LANGCHAIN_API_KEY"] == "langchain-api-key"


def test_parse_secret_map_custom():
    m = parse_secret_map("MY_ENV:my-secret,OTHER:other")
    assert m == {"MY_ENV": "my-secret", "OTHER": "other"}


def test_vault_credential_prefers_databricks_apps_sp(monkeypatch):
    monkeypatch.setenv("DATABRICKS_CLIENT_ID", "apps-sp-id")
    monkeypatch.setenv("DATABRICKS_CLIENT_SECRET", "apps-sp-secret")
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-guid")
    monkeypatch.delenv("EDIM_KV_CLIENT_ID", raising=False)
    monkeypatch.delenv("EDIM_KV_CLIENT_SECRET", raising=False)

    from edim_dde_domain.security.keyvault import _vault_credential

    cred, source = _vault_credential()
    assert "Apps SP" in source
    assert cred.__class__.__name__ == "ClientSecretCredential"


def test_vault_credential_prefers_explicit_kv_reader(monkeypatch):
    monkeypatch.setenv("EDIM_KV_CLIENT_ID", "kv-reader-id")
    monkeypatch.setenv("EDIM_KV_CLIENT_SECRET", "kv-reader-secret")
    monkeypatch.setenv("EDIM_KV_TENANT_ID", "tenant-guid")
    monkeypatch.setenv("DATABRICKS_CLIENT_ID", "apps-sp-id")
    monkeypatch.setenv("DATABRICKS_CLIENT_SECRET", "apps-sp-secret")

    from edim_dde_domain.security.keyvault import _vault_credential

    cred, source = _vault_credential()
    assert source == "EDIM_KV_CLIENT_*"
    assert cred.__class__.__name__ == "ClientSecretCredential"


def test_should_set_env_respects_existing_unless_force(monkeypatch):
    from edim_dde_domain.security.keyvault import _should_set_env

    monkeypatch.setenv("EDIM_FOUNDRY_CLIENT_ID", "already")
    monkeypatch.delenv("EDIM_KV_FORCE", raising=False)
    assert _should_set_env("EDIM_FOUNDRY_CLIENT_ID") is False

    monkeypatch.setenv("EDIM_KV_FORCE", "1")
    assert _should_set_env("EDIM_FOUNDRY_CLIENT_ID") is True
