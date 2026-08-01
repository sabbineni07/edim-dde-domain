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
    assert m["azure-client-id"] == "AZURE_CLIENT_ID"
    assert m["langchain-api-key"] == "LANGCHAIN_API_KEY"


def test_parse_secret_map_custom():
    m = parse_secret_map("my-secret:MY_ENV,other:OTHER")
    assert m == {"my-secret": "MY_ENV", "other": "OTHER"}
