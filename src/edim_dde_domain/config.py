"""Env-driven domain settings (Databricks SQL + Azure Foundry).

Business purpose
----------------
Single Pydantic settings object for warehouse host/path, Unity Catalog table
FQNs, and Foundry endpoint/SP credentials. Used by SQL tools, Foundry LLM,
and startup validation — never hard-codes secrets.

Public API
----------
* ``strip_hostname`` / ``normalize_http_path`` — host/path normalization helpers
* ``DomainSettings`` — env-backed settings model
* ``get_settings`` — process-cached settings instance
* ``clear_settings_cache`` — test helper to drop the cache
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

_WAREHOUSE_ID_RE = re.compile(r"^[0-9a-f]{16,}$", re.IGNORECASE)


def strip_hostname(host: str) -> str:
    """Normalize a Databricks host to bare hostname (no scheme / trailing slash).

    Args:
        host: Raw host, URL, or empty string.

    Returns:
        Hostname suitable for the SQL connector ``server_hostname``.

    Examples::

        strip_hostname("https://adb.azuredatabricks.net/")
        # → "adb.azuredatabricks.net"
    """
    raw = (host or "").strip()
    if raw.startswith("https://"):
        raw = raw[8:]
    elif raw.startswith("http://"):
        raw = raw[7:]
    return raw.rstrip("/")


def normalize_http_path(http_path: Optional[str]) -> str:
    """Normalize warehouse HTTP path or bare warehouse id to ``/sql/1.0/warehouses/...``.

    Falls back to ``DATABRICKS_HTTP_PATH`` or ``SQL_WAREHOUSE_ID`` when
    ``http_path`` is empty.

    Args:
        http_path: Full path, warehouse id hex, or ``None``/empty.

    Returns:
        Normalized path string, or ``""`` if nothing configured.
    """
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

    Reads standard ``DATABRICKS_*`` and Foundry env vars (see ``.env.example``).
    Extra env keys are ignored so shared host ``.env`` files stay safe.
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
        """Bare SQL warehouse hostname (``DATABRICKS_SERVER_HOSTNAME`` or ``DATABRICKS_HOST``)."""
        return strip_hostname(self.databricks_server_hostname or self.databricks_host)

    @property
    def sql_http_path(self) -> str:
        """Normalized warehouse HTTP path."""
        return normalize_http_path(self.databricks_http_path)

    def foundry_sp_credentials(self) -> tuple[str, str, str]:
        """Return (tenant_id, client_id, client_secret) for Foundry SP auth.

        Prefers ``EDIM_FOUNDRY_*``. Falls back to legacy ``AZURE_CLIENT_*`` /
        ``AZURE_TENANT_ID`` when the dedicated vars are incomplete. Allows
        mixing (e.g. dedicated client + shared tenant).

        Returns:
            Three-tuple of strings (any may be empty if unset).
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
        """True when hostname and HTTP path are both non-empty after normalization."""
        return bool(self.sql_hostname and self.sql_http_path)

    def foundry_configured(self) -> bool:
        """True when ``AZURE_OPENAI_ENDPOINT`` is set (token auth checked at invoke)."""
        return bool(self.azure_openai_endpoint.strip())

    def spark_tables_configured(self) -> bool:
        """True when at least one Spark RCA table FQN env is set."""
        return bool(
            self.databricks_spark_logs_table.strip()
            or self.databricks_spark_metrics_table.strip()
        )

    def cluster_metrics_configured(self) -> bool:
        """True when the cluster-tuning metrics table FQN env is set."""
        return bool(self.databricks_job_cluster_metrics_table.strip())


@lru_cache
def get_settings() -> DomainSettings:
    """Return the process-cached ``DomainSettings`` instance.

    Returns:
        Cached settings built from the current environment / ``.env``.
    """
    return DomainSettings()


def clear_settings_cache() -> None:
    """Test helper: drop cached settings so the next ``get_settings()`` reloads."""
    get_settings.cache_clear()
