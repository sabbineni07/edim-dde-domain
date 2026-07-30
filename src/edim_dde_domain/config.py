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

    # Azure AI Foundry (OpenAI v1). Client id/secret may be injected from Key Vault in prod.
    azure_openai_endpoint: str = ""
    azure_openai_deployment_name: str = "gpt-4o"
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""

    @property
    def sql_hostname(self) -> str:
        return strip_hostname(self.databricks_server_hostname or self.databricks_host)

    @property
    def sql_http_path(self) -> str:
        return normalize_http_path(self.databricks_http_path)

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
