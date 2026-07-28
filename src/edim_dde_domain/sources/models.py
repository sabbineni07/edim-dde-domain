"""Named data sources (connections). Secrets stay in env."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceSpec:
    """Unresolved source definition from sources.yaml."""

    name: str
    type: str
    server_hostname: str
    http_path: str
    auth_mode: str = "auto"
    token_env: str = "DATABRICKS_TOKEN"
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class ResolvedSource:
    """Connection-ready source (token resolved)."""

    name: str
    type: str
    server_hostname: str
    http_path: str
    access_token: str

    def connection_params(self) -> dict[str, Any]:
        return {
            "server_hostname": self.server_hostname,
            "http_path": self.http_path,
            "access_token": self.access_token,
            "_socket_timeout": 300,
            "_query_timeout": 0,
        }
