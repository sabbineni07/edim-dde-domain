"""Tests for startup env validation."""

from __future__ import annotations

import pytest

from edim_dde_domain.config import DomainSettings, clear_settings_cache
from edim_dde_domain.startup import inspect_runtime_env, validate_runtime_env


@pytest.fixture(autouse=True)
def _clear_settings():
    clear_settings_cache()
    yield
    clear_settings_cache()


def test_inspect_warns_when_foundry_missing():
    cfg = DomainSettings(
        azure_openai_endpoint="",
        databricks_host="",
        databricks_http_path="",
    )
    result = inspect_runtime_env(cfg)
    assert result.ok  # non-strict inspect never fills errors without env flag
    assert any("AZURE_OPENAI_ENDPOINT" in w for w in result.warnings)


def test_validate_strict_raises_without_foundry(monkeypatch):
    monkeypatch.setenv("EDIM_STRICT_STARTUP", "1")
    monkeypatch.delenv("EDIM_REQUIRE_SQL", raising=False)
    cfg = DomainSettings(
        azure_openai_endpoint="",
        databricks_host="adb.example",
        databricks_http_path="/sql/1.0/warehouses/abc",
    )
    with pytest.raises(RuntimeError, match="FOUNDRY|AZURE_OPENAI"):
        validate_runtime_env(cfg, strict=True)


def test_validate_strict_ok_with_foundry():
    cfg = DomainSettings(
        azure_openai_endpoint="https://example.openai.azure.com",
        azure_openai_deployment_name="gpt-4o",
        databricks_host="",
        databricks_http_path="",
    )
    result = validate_runtime_env(cfg, strict=True)
    assert result.ok
    assert any("DATABRICKS" in w for w in result.warnings)
