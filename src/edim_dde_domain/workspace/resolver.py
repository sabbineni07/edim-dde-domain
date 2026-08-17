"""WorkspaceResolver implementations (catalog + process-env fallback).

Business purpose
----------------
Strategy implementations for within-env SQL targeting:

* ``CatalogWorkspaceResolver`` — pick among YAML workspaces inside ``EDIM_ENV``
* ``ProcessEnvWorkspaceResolver`` — single synthetic workspace from ``DATABRICKS_*``
  (backward compatible when no catalog entries match the process env)

Both fail closed on unknown ids and on ``edim_env`` mismatches.

Public API
----------
* ``ProcessEnvWorkspaceResolver``
* ``CatalogWorkspaceResolver``
* ``build_workspace_resolver`` — factory: catalog if non-empty else process-env
"""

from __future__ import annotations

import os
from typing import Mapping, Optional

from edim_dde_domain.config import normalize_http_path, strip_hostname
from edim_dde_domain.errors import DomainToolError
from edim_dde_domain.workspace.models import TABLE_ENV_ALIASES, WorkspaceDataset


def _require_process_env(edim_env: str) -> str:
    env = (edim_env or "").strip().lower()
    if not env:
        raise DomainToolError(
            "EDIM_ENV is unset; cannot resolve workspace datasets (fail closed)"
        )
    return env


def _assert_same_env(dataset: WorkspaceDataset, process_env: str) -> WorkspaceDataset:
    """Fail closed if a dataset would leave the process env."""
    if dataset.edim_env.strip().lower() != process_env:
        raise DomainToolError(
            f"Workspace {dataset.workspace_id!r} belongs to env "
            f"{dataset.edim_env!r} but process EDIM_ENV={process_env!r} "
            "(agents must never cross env boundaries)"
        )
    return dataset


class ProcessEnvWorkspaceResolver:
    """Single within-env dataset built from process ``DATABRICKS_*`` env vars.

    Used when ``workspaces.yaml`` has no entries for the process ``EDIM_ENV``.
    Preserves today's one-warehouse / one-FQN-set behaviour.
    """

    def __init__(
        self,
        *,
        edim_env: str,
        workspace_id: str = "default",
        environ: Optional[Mapping[str, str]] = None,
    ) -> None:
        self._edim_env = _require_process_env(edim_env)
        wid = (workspace_id or "default").strip() or "default"
        self._workspace_id = wid
        self._environ = environ if environ is not None else os.environ

    @property
    def edim_env(self) -> str:
        return self._edim_env

    def default_workspace_id(self) -> str:
        return self._workspace_id

    def list_workspace_ids(self) -> list[str]:
        return [self._workspace_id]

    def resolve(self, workspace_id: Optional[str] = None) -> WorkspaceDataset:
        requested = (workspace_id or "").strip() or self._workspace_id
        if requested != self._workspace_id:
            raise DomainToolError(
                f"Unknown workspace_id {requested!r} for EDIM_ENV={self._edim_env!r}; "
                f"known: {[self._workspace_id]} "
                "(add workspaces.yaml entries for multi-workspace within this env)"
            )
        env = self._environ
        host = strip_hostname(
            str(env.get("DATABRICKS_HOST") or env.get("DATABRICKS_SERVER_HOSTNAME") or "")
        )
        path = normalize_http_path(str(env.get("DATABRICKS_HTTP_PATH") or ""))
        tables: dict[str, str] = {}
        for logical, env_name in TABLE_ENV_ALIASES.items():
            fqn = str(env.get(env_name) or "").strip()
            if fqn:
                tables[logical] = fqn
        return _assert_same_env(
            WorkspaceDataset(
                workspace_id=self._workspace_id,
                edim_env=self._edim_env,
                server_hostname=host,
                http_path=path,
                tables=tables,
            ),
            self._edim_env,
        )


class CatalogWorkspaceResolver:
    """Resolve among YAML catalog workspaces already filtered to ``EDIM_ENV``."""

    def __init__(
        self,
        datasets: Mapping[str, WorkspaceDataset],
        *,
        edim_env: str,
        default_workspace_id: Optional[str] = None,
    ) -> None:
        self._edim_env = _require_process_env(edim_env)
        if not datasets:
            raise DomainToolError(
                "CatalogWorkspaceResolver requires at least one within-env workspace"
            )
        # Re-validate every entry at construction (defense in depth).
        self._datasets: dict[str, WorkspaceDataset] = {}
        for wid, ds in datasets.items():
            self._datasets[wid] = _assert_same_env(ds, self._edim_env)

        explicit = (default_workspace_id or "").strip()
        if explicit:
            if explicit not in self._datasets:
                raise DomainToolError(
                    f"EDIM_DEFAULT_WORKSPACE_ID={explicit!r} is not in the "
                    f"catalog for EDIM_ENV={self._edim_env!r}; "
                    f"known: {sorted(self._datasets)}"
                )
            self._default_id = explicit
        elif len(self._datasets) == 1:
            self._default_id = next(iter(self._datasets))
        else:
            raise DomainToolError(
                f"Multiple workspaces for EDIM_ENV={self._edim_env!r} "
                f"({sorted(self._datasets)}); set EDIM_DEFAULT_WORKSPACE_ID "
                "or pass workspace_id on the request"
            )

    @property
    def edim_env(self) -> str:
        return self._edim_env

    def default_workspace_id(self) -> str:
        return self._default_id

    def list_workspace_ids(self) -> list[str]:
        return sorted(self._datasets)

    def resolve(self, workspace_id: Optional[str] = None) -> WorkspaceDataset:
        requested = (workspace_id or "").strip() or self._default_id
        ds = self._datasets.get(requested)
        if ds is None:
            raise DomainToolError(
                f"Unknown workspace_id {requested!r} for EDIM_ENV={self._edim_env!r}; "
                f"known: {sorted(self._datasets)}"
            )
        return _assert_same_env(ds, self._edim_env)


def build_workspace_resolver(
    datasets: Mapping[str, WorkspaceDataset],
    *,
    edim_env: str,
    default_workspace_id: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> ProcessEnvWorkspaceResolver | CatalogWorkspaceResolver:
    """Factory: catalog resolver when non-empty, else process-env fallback.

    Args:
        datasets: Within-env catalog (already filtered).
        edim_env: Process ``EDIM_ENV``.
        default_workspace_id: Optional default when catalog has multiple entries.
        environ: Env for process-env fallback construction.

    Returns:
        A ``WorkspaceResolver`` implementation.
    """
    if datasets:
        return CatalogWorkspaceResolver(
            datasets,
            edim_env=edim_env,
            default_workspace_id=default_workspace_id,
        )
    env_map = environ if environ is not None else os.environ
    fallback_id = (default_workspace_id or "").strip() or "default"
    return ProcessEnvWorkspaceResolver(
        edim_env=edim_env,
        workspace_id=fallback_id,
        environ=env_map,
    )
