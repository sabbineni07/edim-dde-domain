"""Immutable workspace / dataset models for within-env SQL resolution.

Business purpose
----------------
A single EDIM process is bound to one ``EDIM_ENV``. Inside that env there may
be multiple Databricks workspaces (e.g. ``dev_1``, ``dev_2``). These models
carry the warehouse host/path and Unity Catalog table FQNs for one workspace
**inside the process env only**.

Public API
----------
* ``TABLE_ENV_ALIASES`` — logical table key → ``${ENV}`` name used in agent SQL
* ``WorkspaceDataset`` — resolved host/path + tables for one workspace
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


# Logical keys in workspaces.yaml ``tables:`` → env names interpolated in agent SQL.
TABLE_ENV_ALIASES: Mapping[str, str] = {
    "job_cluster_metrics": "DATABRICKS_JOB_CLUSTER_METRICS_TABLE",
    "spark_metrics": "DATABRICKS_SPARK_METRICS_TABLE",
    "spark_logs": "DATABRICKS_SPARK_LOGS_TABLE",
}


@dataclass(frozen=True)
class WorkspaceDataset:
    """Connection + UC dataset for one Databricks workspace inside ``edim_env``.

    Attributes:
        workspace_id: Caller-facing id (e.g. ``dev_1`` or ``default``).
        edim_env: EDIM environment this dataset belongs to (must match process).
        server_hostname: Databricks SQL warehouse hostname (normalized).
        http_path: Warehouse HTTP path (normalized).
        tables: Logical table key → UC FQN (``catalog.schema.table``).
    """

    workspace_id: str
    edim_env: str
    server_hostname: str = ""
    http_path: str = ""
    tables: Mapping[str, str] = field(default_factory=dict)

    def as_sql_environ(self) -> dict[str, str]:
        """Map logical tables onto the env names used by agent YAML ``${VAR}``.

        Returns:
            Overlay suitable for merging into ``prepare_query`` environ so
            ``${DATABRICKS_*_TABLE}`` picks this workspace's FQNs.
        """
        out: dict[str, str] = {}
        for logical, fqn in self.tables.items():
            env_name = TABLE_ENV_ALIASES.get(logical)
            if env_name and fqn:
                out[env_name] = fqn
        return out
