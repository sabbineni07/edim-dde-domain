"""Domain configuration for Databricks SQL warehouse access."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

_WAREHOUSE_ID_RE = re.compile(r"^[0-9a-f]{16,}$", re.IGNORECASE)


def strip_hostname(host: str) -> str:
    raw = (host or "").strip()
    if raw.startswith("https://"):
        raw = raw[8:]
    elif raw.startswith("http://"):
        raw = raw[7:]
    return raw.rstrip("/")


def normalize_http_path(http_path: Optional[str]) -> str:
    raw = (http_path or "").strip()
    if not raw:
        raw = (
            os.environ.get("DATABRICKS_HTTP_PATH") or os.environ.get("SQL_WAREHOUSE_ID") or ""
        ).strip()
    if not raw:
        return ""
    if raw.startswith("/sql/"):
        return raw
    if _WAREHOUSE_ID_RE.match(raw) or "/" not in raw:
        return f"/sql/1.0/warehouses/{raw}"
    return raw


class DomainSettings(BaseSettings):
    """Env-driven Databricks SQL + table names for domain tools.

    Reads standard ``DATABRICKS_*`` env vars (see ``.env.example``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    databricks_host: str = ""
    databricks_server_hostname: str = ""
    databricks_http_path: str = ""

    databricks_spark_logs_table: str = ""
    databricks_spark_metrics_table: str = ""
    databricks_job_cluster_metrics_table: str = ""

    # Azure AI Foundry (OpenAI v1). Prefer EDIM_FOUNDRY_* so DefaultAzureCredential
    # (SQL) is not polluted by Foundry SP env names.
    azure_openai_endpoint: str = ""
    azure_openai_deployment_name: str = "gpt-4o"
    edim_foundry_tenant_id: str = ""
    edim_foundry_client_id: str = ""
    edim_foundry_client_secret: str = ""
    # Legacy Foundry SP names (deprecated — EnvironmentCredential / SQL also read these).
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""

    @property
    def sql_hostname(self) -> str:
        return strip_hostname(self.databricks_server_hostname or self.databricks_host)

    @property
    def sql_http_path(self) -> str:
        return normalize_http_path(self.databricks_http_path)

    def foundry_sp_credentials(self) -> tuple[str, str, str]:
        """Return (tenant_id, client_id, client_secret) for Foundry SP auth.

        Prefers ``EDIM_FOUNDRY_*``. Falls back to legacy ``AZURE_CLIENT_*`` /
        ``AZURE_TENANT_ID`` when the dedicated vars are incomplete.
        """
        tenant = (self.edim_foundry_tenant_id or "").strip()
        client_id = (self.edim_foundry_client_id or "").strip()
        client_secret = (self.edim_foundry_client_secret or "").strip()
        if tenant and client_id and client_secret:
            return tenant, client_id, client_secret

        legacy_tenant = (self.azure_tenant_id or "").strip()
        legacy_id = (self.azure_client_id or "").strip()
        legacy_secret = (self.azure_client_secret or "").strip()
        # Allow mixing: e.g. EDIM_FOUNDRY_CLIENT_* + shared AZURE_TENANT_ID.
        tenant = tenant or legacy_tenant
        client_id = client_id or legacy_id
        client_secret = client_secret or legacy_secret
        return tenant, client_id, client_secret

    def sql_configured(self) -> bool:
        return bool(self.sql_hostname and self.sql_http_path)

    def foundry_configured(self) -> bool:
        return bool(self.azure_openai_endpoint.strip())

    def spark_tables_configured(self) -> bool:
        return bool(
            self.databricks_spark_logs_table.strip()
            or self.databricks_spark_metrics_table.strip()
        )

    def cluster_metrics_configured(self) -> bool:
        return bool(self.databricks_job_cluster_metrics_table.strip())


@lru_cache
def get_settings() -> DomainSettings:
    return DomainSettings()


def clear_settings_cache() -> None:
    """Test helper: drop cached settings."""
    get_settings.cache_clear()
