"""Process-wide workspace resolver registry.

Business purpose
----------------
Load ``workspaces.yaml`` once at bootstrap (filtered to ``EDIM_ENV``) and expose
``resolve_workspace_dataset`` for ``domain.sql.query``. Mirrors the sources
registry pattern.

Public API
----------
* ``load_workspace_resolver`` / ``ensure_workspace_resolver_loaded``
* ``clear_workspace_resolver``
* ``get_workspace_resolver`` / ``resolve_workspace_dataset``
* ``try_resolve_workspace_dataset`` — ``None`` when resolver not configured
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional

from edim_dde_domain.errors import DomainToolError
from edim_dde_domain.workspace.catalog import (
    default_workspaces_path,
    load_workspaces_file,
)
from edim_dde_domain.workspace.models import TABLE_ENV_ALIASES, WorkspaceDataset
from edim_dde_domain.workspace.protocols import WorkspaceResolver
from edim_dde_domain.workspace.resolver import (
    CatalogWorkspaceResolver,
    ProcessEnvWorkspaceResolver,
    build_workspace_resolver,
)

_RESOLVER: WorkspaceResolver | None = None
_LOADED_PATH: Path | None = None

__all__ = [
    "TABLE_ENV_ALIASES",
    "CatalogWorkspaceResolver",
    "ProcessEnvWorkspaceResolver",
    "WorkspaceDataset",
    "WorkspaceResolver",
    "build_workspace_resolver",
    "clear_workspace_resolver",
    "default_workspaces_path",
    "ensure_workspace_resolver_loaded",
    "get_workspace_resolver",
    "load_workspace_resolver",
    "load_workspaces_file",
    "resolve_workspace_dataset",
    "try_resolve_workspace_dataset",
]


def clear_workspace_resolver() -> None:
    """Drop the in-process resolver (used by ``reset_bootstrap`` in tests)."""
    global _RESOLVER, _LOADED_PATH
    _RESOLVER = None
    _LOADED_PATH = None


def load_workspace_resolver(
    path: str | Path | None = None,
    *,
    edim_env: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
    overwrite: bool = True,
) -> list[str]:
    """Load catalog + install the process workspace resolver.

    When the YAML is missing or has no entries for the process env, installs a
    process-env fallback (single ``default`` workspace from ``DATABRICKS_*``).

    Args:
        path: Explicit ``workspaces.yaml``; ``None`` → default path.
        edim_env: Override ``EDIM_ENV``; default from environ.
        environ: Env mapping for interpolation and defaults.
        overwrite: When false, refuse if a resolver is already loaded.

    Returns:
        Registered workspace ids after load.
    """
    global _RESOLVER, _LOADED_PATH
    if _RESOLVER is not None and not overwrite:
        raise DomainToolError("Workspace resolver already loaded")

    env_map = dict(environ) if environ is not None else dict(os.environ)
    process_env = (
        edim_env if edim_env is not None else env_map.get("EDIM_ENV", "")
    ).strip()

    p = Path(path) if path else default_workspaces_path()
    if not process_env:
        # Catalog requires EDIM_ENV to filter; without it only process-env
        # fallback is allowed (single synthetic workspace, env tag "default").
        fallback_id = (
            str(env_map.get("EDIM_DEFAULT_WORKSPACE_ID") or "").strip() or "default"
        )
        _RESOLVER = ProcessEnvWorkspaceResolver(
            edim_env="default",
            workspace_id=fallback_id,
            environ=env_map,
        )
        _LOADED_PATH = p
        return _RESOLVER.list_workspace_ids()

    datasets = load_workspaces_file(p, edim_env=process_env, environ=env_map)
    default_id = str(env_map.get("EDIM_DEFAULT_WORKSPACE_ID") or "").strip() or None
    _RESOLVER = build_workspace_resolver(
        datasets,
        edim_env=process_env,
        default_workspace_id=default_id,
        environ=env_map,
    )
    _LOADED_PATH = p
    return _RESOLVER.list_workspace_ids()


def ensure_workspace_resolver_loaded(
    path: str | Path | None = None,
    *,
    environ: Optional[Mapping[str, str]] = None,
) -> None:
    """Load the resolver if not yet configured (lazy init for SQL nodes)."""
    if _RESOLVER is None:
        load_workspace_resolver(path, environ=environ)


def get_workspace_resolver() -> WorkspaceResolver:
    """Return the process resolver (loads default catalog if needed)."""
    ensure_workspace_resolver_loaded()
    assert _RESOLVER is not None
    return _RESOLVER


def resolve_workspace_dataset(
    workspace_id: Optional[str] = None,
) -> WorkspaceDataset:
    """Resolve warehouse + UC tables for ``workspace_id`` (or process default).

    Args:
        workspace_id: Requested workspace from agent state / API body.

    Returns:
        ``WorkspaceDataset`` guaranteed to belong to the process ``EDIM_ENV``.

    Raises:
        DomainToolError: Unknown id or env-boundary violation.
    """
    return get_workspace_resolver().resolve(workspace_id)


def try_resolve_workspace_dataset(
    workspace_id: Optional[str] = None,
) -> WorkspaceDataset | None:
    """Like ``resolve_workspace_dataset`` but returns ``None`` on DomainToolError.

    Prefer ``resolve_workspace_dataset`` in production SQL paths so misconfig
    fails closed. This helper is for optional overlays / diagnostics.
    """
    try:
        return resolve_workspace_dataset(workspace_id)
    except DomainToolError:
        return None
