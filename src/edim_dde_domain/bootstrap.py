"""Register domain node types and load agent YAML graphs once."""

from __future__ import annotations

from pathlib import Path

from edim_dde_ai import register_from_yaml

from edim_dde_domain.sources import load_sources

# Importing nodes registers @register_node factories.
from edim_dde_domain.nodes import sql_query as _sql_query_nodes  # noqa: F401
from edim_dde_domain.agents.cluster_tuning import nodes as _tuning_nodes  # noqa: F401
from edim_dde_domain.agents.spark_rca import nodes as _rca_nodes  # noqa: F401

_AGENTS_DIR = Path(__file__).resolve().parent / "agents"
_READY = False


def bootstrap_agents() -> None:
    """Idempotent: load sources + register domain agent graphs into edim-dde-ai.

    Call once at API/app startup (before ``create_agent``). Does **not** set an
    LLM provider — hosts must call ``set_llm_provider(...)`` for llm_chain nodes.
    """
    global _READY
    load_sources()
    if _READY:
        return
    register_from_yaml(_AGENTS_DIR / "spark_rca" / "spark_rca.agent.yaml", overwrite=True)
    register_from_yaml(
        _AGENTS_DIR / "cluster_tuning" / "cluster_tuning.agent.yaml", overwrite=True
    )
    _READY = True


def reset_bootstrap() -> None:
    """Allow re-bootstrap after clearing sources (tests)."""
    global _READY
    from edim_dde_domain.sources import clear_sources

    _READY = False
    clear_sources()
