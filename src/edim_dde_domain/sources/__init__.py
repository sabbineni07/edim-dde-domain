"""In-process registry of named sources."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from edim_dde_domain.errors import DomainToolError
from edim_dde_domain.sources.loader import default_sources_path, load_sources_file
from edim_dde_domain.sources.models import ResolvedSource, SourceSpec
from edim_dde_domain.sources.resolve import try_resolve_source

_SPECS: dict[str, SourceSpec] = {}
_LOADED_PATH: Path | None = None


def clear_sources() -> None:
    global _SPECS, _LOADED_PATH
    _SPECS = {}
    _LOADED_PATH = None


def load_sources(path: str | Path | None = None, *, overwrite: bool = True) -> list[str]:
    """Load sources.yaml into the registry. Returns source names."""
    global _SPECS, _LOADED_PATH
    specs = load_sources_file(path)
    if overwrite:
        _SPECS = dict(specs)
    else:
        for name, spec in specs.items():
            if name in _SPECS:
                raise DomainToolError(f"Source already registered: {name}")
            _SPECS[name] = spec
    _LOADED_PATH = Path(path) if path else default_sources_path()
    return list(_SPECS.keys())


def ensure_sources_loaded(path: str | Path | None = None) -> None:
    if not _SPECS:
        load_sources(path)


def get_source_spec(name: str) -> SourceSpec:
    ensure_sources_loaded()
    if name not in _SPECS:
        raise DomainToolError(
            f"Unknown source {name!r}. Known: {sorted(_SPECS) or '(none)'}"
        )
    return _SPECS[name]


def get_resolved_source(name: str) -> ResolvedSource:
    """Resolve a source for SQL execution (raises if not configured)."""
    from edim_dde_domain.sources.resolve import resolve_source

    return resolve_source(get_source_spec(name))


def try_get_resolved_source(name: str) -> ResolvedSource | None:
    return try_resolve_source(get_source_spec(name))


def list_sources() -> list[str]:
    ensure_sources_loaded()
    return sorted(_SPECS)
