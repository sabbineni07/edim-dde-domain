"""Register domain node types and load agent YAML graphs once.

Business purpose
----------------
One-shot process bootstrap for API / hosts: load ``sources.yaml``, corpora,
experience transforms, quality evaluators, shared ``domain.sql.query``, then
discover packaged (and optional external) ``*.agent.yaml`` graphs. Does **not**
set an LLM provider — hosts must call ``set_llm_provider(...)``.

Public API
----------
* ``bootstrap_agents`` — idempotent full registration (thread-safe)
* ``load_external_agents`` — dirs / ``EDIM_AGENT_DIRS`` + entry points
* ``reset_bootstrap`` — test helper to allow a fresh bootstrap
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import sys
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from edim_dde_ai import register_from_directory
from edim_dde_ai.errors import LoaderError

from edim_dde_domain.errors import DomainToolError
from edim_dde_domain.sources import load_sources

# Shared node type (not under a single agent package).
from edim_dde_domain.nodes import sql_query as _sql_query_nodes  # noqa: F401

_AGENTS_DIR = Path(__file__).resolve().parent / "agents"
_ENTRY_POINT_GROUP = "edim_dde.agents"
_READY = False
_LOCK = threading.Lock()
logger = logging.getLogger(__name__)


def _import_packaged_agent_nodes() -> None:
    """Import bundled ``agents/<pkg>/nodes.py`` so ``@register_node`` factories load."""
    for nodes_py in sorted(_AGENTS_DIR.glob("*/nodes.py")):
        pkg = nodes_py.parent.name
        if pkg.startswith("_") or not pkg.isidentifier():
            continue
        importlib.import_module(f"edim_dde_domain.agents.{pkg}.nodes")


def _import_nodes_py_files(root: Path) -> list[str]:
    """Load every ``nodes.py`` under ``root`` via file location (external trees).

    Args:
        root: Directory tree that may contain nested ``nodes.py`` files.

    Returns:
        Paths of modules successfully loaded (skipping already-imported names).
    """
    loaded: list[str] = []
    for nodes_py in sorted(root.rglob("nodes.py")):
        if any(part.startswith(".") or part == "__pycache__" for part in nodes_py.parts):
            continue
        rel = nodes_py.relative_to(root).with_suffix("")
        mod_name = "edim_dde_ext_" + "_".join(rel.parts)
        if mod_name in sys.modules:
            continue
        spec = importlib.util.spec_from_file_location(mod_name, nodes_py)
        if spec is None or spec.loader is None:
            raise DomainToolError(f"Cannot import external nodes module: {nodes_py}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)
        loaded.append(str(nodes_py))
    return loaded


def _parse_agent_dirs(
    dirs: Sequence[str | Path] | None,
) -> list[Path]:
    """Resolve external agent directory list from args or ``EDIM_AGENT_DIRS``."""
    if dirs is not None:
        raw = [str(d).strip() for d in dirs if str(d).strip()]
    else:
        env = os.environ.get("EDIM_AGENT_DIRS", "").strip()
        if not env:
            raw = []
        elif os.pathsep in env:
            raw = [p.strip() for p in env.split(os.pathsep) if p.strip()]
        else:
            # Comma-separated is convenient in .env files on all platforms
            raw = [p.strip() for p in env.split(",") if p.strip()]
    out: list[Path] = []
    for item in raw:
        path = Path(item).expanduser()
        if not path.is_dir():
            raise DomainToolError(f"External agent directory does not exist: {path}")
        out.append(path.resolve())
    return out


def _load_entry_point_plugins(group: str = _ENTRY_POINT_GROUP) -> list[str]:
    """Load ``edim_dde.agents`` entry points (callables register agents/nodes).

    Args:
        group: Packaging entry-point group name.

    Returns:
        Entry-point names that were invoked.
    """
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover
        return []

    selected: Any
    eps = entry_points()
    if hasattr(eps, "select"):
        selected = list(eps.select(group=group))
    else:  # pragma: no cover — older importlib.metadata
        selected = list(eps.get(group, []))

    names: list[str] = []
    for ep in selected:
        plugin = ep.load()
        if not callable(plugin):
            raise DomainToolError(
                f"Entry point {ep.name!r} in group {group!r} must be callable "
                f"(got {type(plugin).__name__})"
            )
        plugin()
        names.append(ep.name)
        logger.info("loaded_agent_entry_point", extra={"name": ep.name, "group": group})
    return names


def load_external_agents(
    dirs: Sequence[str | Path] | None = None,
    *,
    entry_points: bool = True,
    entry_point_group: str = _ENTRY_POINT_GROUP,
    overwrite: bool = True,
) -> list[str]:
    """Register agents from external directories and/or packaging entry points.

    Directory layout matches bundled agents (recursive ``*.agent.yaml`` plus
    optional ``nodes.py`` files). When ``dirs`` is omitted, reads
    ``EDIM_AGENT_DIRS`` (``os.pathsep``- or comma-separated paths).

    Entry points use group ``edim_dde.agents`` (override with
    ``entry_point_group``). Each entry point must be a zero-arg callable that
    registers nodes/YAML (typically ``register_from_directory`` + imports).

    Args:
        dirs: Explicit agent roots; ``None`` → env ``EDIM_AGENT_DIRS``.
        entry_points: When true, also load packaging plugins.
        entry_point_group: Override for the entry-point group name.
        overwrite: Passed to ``register_from_directory``.

    Returns:
        Registered agent ids from directory scans (entry-point plugins
        register themselves and are listed only by entry-point name in logs).
    """
    agent_ids: list[str] = []
    for root in _parse_agent_dirs(dirs):
        _import_nodes_py_files(root)
        try:
            ids = register_from_directory(
                root,
                pattern="*.agent.yaml",
                overwrite=overwrite,
                recursive=True,
            )
        except LoaderError as exc:
            raise DomainToolError(
                f"No agent YAML found under external dir {root}: {exc}"
            ) from exc
        agent_ids.extend(ids)
        logger.info(
            "loaded_external_agent_dir",
            extra={"dir": str(root), "agent_ids": ids},
        )

    if entry_points:
        _load_entry_point_plugins(entry_point_group)

    return agent_ids


def bootstrap_agents(*, load_external: bool = True) -> None:
    """Idempotent: load sources + register bundled (and optional external) agents.

    Discovers agents recursively under package ``agents/``. Also imports each
    ``agents/<pkg>/nodes.py`` so node factories are registered.

    When ``load_external`` is true (default), also calls
    :func:`load_external_agents` (``EDIM_AGENT_DIRS`` + ``edim_dde.agents``
    entry points).

    Call once at API/app startup (before ``create_agent``). Does **not** set an
    LLM provider — hosts must call ``set_llm_provider(...)`` for llm_chain nodes.

    Thread-safe. After the first successful registration, later calls are no-ops.
    Call ``reset_bootstrap()`` in tests to allow a fresh load.

    Args:
        load_external: When false, skip external dirs / entry points (unit tests).
    """
    global _READY
    with _LOCK:
        if _READY:
            return
        load_sources()
        _load_corpora()
        _register_experience_transforms()
        _register_evaluators()
        _import_packaged_agent_nodes()
        try:
            ids = register_from_directory(
                _AGENTS_DIR,
                pattern="*.agent.yaml",
                overwrite=True,
                recursive=True,
            )
        except LoaderError as exc:
            raise DomainToolError(
                f"No agent YAML found under {_AGENTS_DIR}: {exc}"
            ) from exc
        logger.info(
            "bootstrapped_agents",
            extra={"agent_ids": ids, "agents_dir": str(_AGENTS_DIR)},
        )
        if load_external:
            # dirs=None → EDIM_AGENT_DIRS + entry points
            load_external_agents()
        _READY = True


def _load_corpora() -> None:
    """Register logical corpora from packaged ``config/corpora.yaml`` if present."""
    path = Path(__file__).resolve().parent / "config" / "corpora.yaml"
    if not path.is_file():
        return
    try:
        from edim_dde_ai.retrieval import load_corpora_yaml

        loaded = load_corpora_yaml(path)
        logger.info(
            "loaded_corpora",
            extra={"path": str(path), "corpora": [c.name for c in loaded]},
        )
    except Exception as exc:  # noqa: BLE001 — bootstrap should not hard-fail
        logger.warning("corpora.yaml load skipped/failed: %s", exc)


def _cluster_tuning_pressure_config() -> dict[str, Any]:
    """Read the packaged agent's pressure policy for non-graph consumers."""
    path = _AGENTS_DIR / "cluster_tuning" / "cluster_tuning.agent.yaml"
    if not path.is_file():
        return {}
    try:
        import yaml

        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        nodes = ((payload.get("graph") or {}).get("nodes") or [])
        for node in nodes:
            if isinstance(node, dict) and node.get("id") == "prepare_sizing_payload":
                config = node.get("resource_pressure")
                return dict(config) if isinstance(config, dict) else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("cluster tuning pressure config load failed: %s", exc)
    return {}


def _register_experience_transforms() -> None:
    """Register domain ExperienceTransforms (feature/action index parsers)."""
    try:
        from edim_dde_domain.agents.cluster_tuning.helpers.experience_transform import (
            register_cluster_tuning_experience_transform,
        )
        from edim_dde_domain.agents.spark_rca.helpers.experience_transform import (
            register_spark_rca_experience_transform,
        )

        register_cluster_tuning_experience_transform(
            _cluster_tuning_pressure_config()
        )
        register_spark_rca_experience_transform()
    except Exception as exc:  # noqa: BLE001
        logger.warning("experience transform registration skipped/failed: %s", exc)


def _register_evaluators() -> None:
    """Register domain quality rubrics with the framework evaluator registry."""
    try:
        from edim_dde_domain.evaluation import (
            register_cluster_tuning_evaluator,
            register_spark_rca_evaluator,
        )

        register_cluster_tuning_evaluator(_cluster_tuning_pressure_config())
        register_spark_rca_evaluator()
    except Exception as exc:  # noqa: BLE001
        logger.warning("evaluator registration skipped/failed: %s", exc)


def reset_bootstrap() -> None:
    """Allow re-bootstrap after clearing sources (tests).

    Clears the in-process sources registry and the ``_READY`` latch so the
    next ``bootstrap_agents()`` runs the full registration path again.
    """
    global _READY
    with _LOCK:
        _READY = False
        from edim_dde_domain.sources import clear_sources

        clear_sources()
