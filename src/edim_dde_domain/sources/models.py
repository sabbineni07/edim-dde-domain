"""Named data sources (connections). Secrets are resolved at runtime.

Business purpose
----------------
Frozen dataclasses for YAML source definitions vs connection-ready snapshots.
``SourceSpec`` may still contain ``${ENV}`` placeholders; ``ResolvedSource``
always carries a concrete host, path, and access token for the SQL connector.

Public API
----------
* ``SourceSpec`` — unresolved definition from ``sources.yaml``
* ``ResolvedSource`` — connection-ready; ``connection_params()`` for the connector
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceSpec:
    """Unresolved source definition from sources.yaml.

    Attributes:
        name: Logical source id referenced by agent YAML ``source:``.
        type: Connection type (currently ``databricks_sql`` only).
        server_hostname: Raw host or ``${ENV}`` placeholder string.
        http_path: Raw path / warehouse id or ``${ENV}`` placeholder.
        raw: Original YAML mapping for the source (optional).
    """

    name: str
    type: str
    server_hostname: str
    http_path: str
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class ResolvedSource:
    """Connection-ready source (token resolved at runtime).

    Attributes:
        name: Logical source id.
        type: Connection type (e.g. ``databricks_sql``).
        server_hostname: Bare hostname (no scheme).
        http_path: Normalized warehouse HTTP path.
        access_token: Databricks SQL bearer token for this request/process.
    """

    name: str
    type: str
    server_hostname: str
    http_path: str
    access_token: str

    def connection_params(self) -> dict[str, Any]:
        """Keyword args for ``databricks.sql.connect`` (plus socket/query timeouts).

        Returns:
            Dict with ``server_hostname``, ``http_path``, ``access_token``, and
            connector timeout knobs (``_socket_timeout``, ``_query_timeout``).
        """
        return {
            "server_hostname": self.server_hostname,
            "http_path": self.http_path,
            "access_token": self.access_token,
            "_socket_timeout": 300,
            "_query_timeout": 0,
        }
