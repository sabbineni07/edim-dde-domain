"""Load and validate ``workspaces.yaml`` (within-env catalog).

Business purpose
----------------
Parse a multi-workspace catalog and **register only entries whose ``env``
matches the process ``EDIM_ENV``. Entries for other envs are ignored at load
(never selectable). Invalid FQNs / missing env fail closed.

Public API
----------
* ``default_workspaces_path`` — repo-root or package default YAML
* ``parse_workspaces_mapping`` — dict → ``{workspace_id: WorkspaceDataset}``
* ``load_workspaces_file`` — read + parse filtered to ``edim_env``
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml

from edim_dde_domain.config import normalize_http_path, strip_hostname
from edim_dde_domain.errors import DomainToolError
from edim_dde_domain.sources.resolve import interpolate_env
from edim_dde_domain.workspace.models import TABLE_ENV_ALIASES, WorkspaceDataset

# Prefer package-shipped config; repo-root config/ is a fallback for local edits.
_PACKAGE_WORKSPACES = (
    Path(__file__).resolve().parents[1] / "config" / "workspaces.yaml"
)
_REPO_WORKSPACES = Path(__file__).resolve().parents[3] / "config" / "workspaces.yaml"
_DEFAULT_WORKSPACES_PATH = (
    _REPO_WORKSPACES if _REPO_WORKSPACES.is_file() else _PACKAGE_WORKSPACES
)

# Same FQN shape as tools.sql.interpolate_sql_env
_SQL_FQN_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){1,2}$"
)

_WORKSPACE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def default_workspaces_path() -> Path:
    """Return the default ``workspaces.yaml`` path (repo root if present)."""
    return _DEFAULT_WORKSPACES_PATH


def _validate_fqn(logical: str, value: str, *, workspace_id: str) -> str:
    fqn = value.strip()
    if not fqn:
        raise DomainToolError(
            f"workspaces.{workspace_id}.tables.{logical} is empty"
        )
    if not _SQL_FQN_RE.fullmatch(fqn):
        raise DomainToolError(
            f"workspaces.{workspace_id}.tables.{logical} must be a "
            f"catalog.schema[.table] identifier (got {fqn!r})"
        )
    return fqn


def parse_workspaces_mapping(
    data: dict[str, Any],
    *,
    edim_env: str,
    environ: Optional[Mapping[str, str]] = None,
) -> dict[str, WorkspaceDataset]:
    """Parse YAML mapping into datasets for ``edim_env`` only.

    Entries whose ``env`` does not equal ``edim_env`` (case-insensitive) are
    **skipped** — they must never be selectable from this process.

    Args:
        data: Top-level YAML mapping (may contain ``workspaces``).
        edim_env: Process environment; required non-empty.
        environ: Env for ``${VAR}`` interpolation in host/path; default ``os.environ``.

    Returns:
        ``{workspace_id: WorkspaceDataset}`` for the process env only.

    Raises:
        DomainToolError: Invalid shape, bad id, missing env field, or bad FQN.
    """
    process_env = (edim_env or "").strip().lower()
    if not process_env:
        raise DomainToolError(
            "EDIM_ENV is required to load workspaces.yaml (fail closed)"
        )

    if not isinstance(data, dict):
        raise DomainToolError("workspaces.yaml must be a mapping")

    raw = data.get("workspaces")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise DomainToolError("workspaces.yaml 'workspaces' must be a mapping")

    env_map = environ if environ is not None else os.environ
    out: dict[str, WorkspaceDataset] = {}

    for workspace_id, item in raw.items():
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            raise DomainToolError("workspace ids must be non-empty strings")
        wid = workspace_id.strip()
        if not _WORKSPACE_ID_RE.fullmatch(wid):
            raise DomainToolError(
                f"Invalid workspace id {wid!r}; use letters/digits/_./- "
                "(max 64 chars)"
            )
        if not isinstance(item, dict):
            raise DomainToolError(f"workspaces.{wid} must be a mapping")

        entry_env = str(item.get("env") or "").strip().lower()
        if not entry_env:
            raise DomainToolError(
                f"workspaces.{wid}.env is required (fail closed on missing env)"
            )
        # Hard rule: never register cross-env entries into this process.
        if entry_env != process_env:
            continue

        host_raw = interpolate_env(str(item.get("server_hostname") or ""), env_map)
        path_raw = interpolate_env(str(item.get("http_path") or ""), env_map)
        host = strip_hostname(host_raw) if host_raw.strip() else ""
        path = normalize_http_path(path_raw) if path_raw.strip() else ""

        tables_raw = item.get("tables") or {}
        if tables_raw is None:
            tables_raw = {}
        if not isinstance(tables_raw, dict):
            raise DomainToolError(f"workspaces.{wid}.tables must be a mapping")

        tables: dict[str, str] = {}
        for logical, fqn in tables_raw.items():
            if not isinstance(logical, str) or not logical.strip():
                raise DomainToolError(
                    f"workspaces.{wid}.tables keys must be non-empty strings"
                )
            key = logical.strip()
            if key not in TABLE_ENV_ALIASES:
                raise DomainToolError(
                    f"workspaces.{wid}.tables unknown key {key!r}; "
                    f"known: {sorted(TABLE_ENV_ALIASES)}"
                )
            if not isinstance(fqn, str):
                raise DomainToolError(
                    f"workspaces.{wid}.tables.{key} must be a string FQN"
                )
            # Allow ${VAR} in FQN fields too, then validate.
            resolved_fqn = interpolate_env(fqn, env_map).strip()
            tables[key] = _validate_fqn(key, resolved_fqn, workspace_id=wid)

        out[wid] = WorkspaceDataset(
            workspace_id=wid,
            edim_env=process_env,
            server_hostname=host,
            http_path=path,
            tables=tables,
        )

    return out


def load_workspaces_file(
    path: str | Path | None = None,
    *,
    edim_env: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> dict[str, WorkspaceDataset]:
    """Read and parse a ``workspaces.yaml`` filtered to the process env.

    Args:
        path: Explicit path; ``None`` uses ``default_workspaces_path()``.
            Missing file → empty catalog (process-env fallback elsewhere).
        edim_env: Override process env; default ``EDIM_ENV`` from environ.
        environ: Env mapping for interpolation and ``EDIM_ENV``.

    Returns:
        Within-env ``{workspace_id: WorkspaceDataset}`` (possibly empty).
    """
    env_map = environ if environ is not None else os.environ
    process_env = (edim_env if edim_env is not None else env_map.get("EDIM_ENV", "")).strip()

    p = Path(path) if path else default_workspaces_path()
    if not p.is_file():
        return {}

    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise DomainToolError(f"{p} must decode to a mapping")
    return parse_workspaces_mapping(data, edim_env=process_env, environ=env_map)
