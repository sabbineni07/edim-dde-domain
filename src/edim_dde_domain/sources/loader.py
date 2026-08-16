"""Load sources.yaml into SourceSpec mappings.

Business purpose
----------------
Parse the packaged (or repo-root) ``sources.yaml`` into frozen ``SourceSpec``
objects. Prefers repo-root ``config/sources.yaml`` when present so local edits
override the package-shipped file without a reinstall.

Public API
----------
* ``default_sources_path`` — resolved default YAML path
* ``parse_sources_mapping`` — dict → ``{name: SourceSpec}``
* ``load_sources_file`` — read + parse a YAML file
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from edim_dde_domain.errors import DomainToolError
from edim_dde_domain.sources.models import SourceSpec

# Prefer package-shipped config; repo-root config/ is a fallback for local edits.
_PACKAGE_SOURCES = Path(__file__).resolve().parents[1] / "config" / "sources.yaml"
_REPO_SOURCES = Path(__file__).resolve().parents[3] / "config" / "sources.yaml"
_DEFAULT_SOURCES_PATH = (
    _REPO_SOURCES if _REPO_SOURCES.is_file() else _PACKAGE_SOURCES
)


def default_sources_path() -> Path:
    """Return the default ``sources.yaml`` path (repo root if present, else package)."""
    return _DEFAULT_SOURCES_PATH


def parse_sources_mapping(data: dict[str, Any]) -> dict[str, SourceSpec]:
    """Parse a decoded YAML mapping into ``SourceSpec`` objects.

    Args:
        data: Top-level mapping that must contain a non-empty ``sources`` dict.

    Returns:
        ``{source_name: SourceSpec}``.

    Raises:
        DomainToolError: Invalid shape or missing required fields.
    """
    if not isinstance(data, dict):
        raise DomainToolError("sources.yaml must be a mapping")
    raw_sources = data.get("sources")
    if not isinstance(raw_sources, dict) or not raw_sources:
        raise DomainToolError("sources.yaml must contain a non-empty 'sources' mapping")

    out: dict[str, SourceSpec] = {}
    for name, item in raw_sources.items():
        if not isinstance(name, str) or not name.strip():
            raise DomainToolError("source names must be non-empty strings")
        if not isinstance(item, dict):
            raise DomainToolError(f"sources.{name} must be a mapping")
        stype = item.get("type")
        if not isinstance(stype, str) or not stype.strip():
            raise DomainToolError(f"sources.{name}.type is required")
        out[name] = SourceSpec(
            name=name,
            type=stype.strip(),
            server_hostname=str(item.get("server_hostname") or ""),
            http_path=str(item.get("http_path") or ""),
            raw=dict(item),
        )
    return out


def load_sources_file(path: str | Path | None = None) -> dict[str, SourceSpec]:
    """Read and parse a ``sources.yaml`` file.

    Args:
        path: Explicit path; ``None`` uses ``default_sources_path()``.

    Returns:
        ``{source_name: SourceSpec}``.

    Raises:
        DomainToolError: Missing file or invalid YAML shape.
    """
    p = Path(path) if path else default_sources_path()
    if not p.is_file():
        raise DomainToolError(f"sources file not found: {p}")
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise DomainToolError(f"{p} must decode to a mapping")
    return parse_sources_mapping(data)
