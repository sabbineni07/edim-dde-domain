"""LangGraph Agent Server entrypoints for EDIM domain agents.

This module is a host adapter, not a second graph implementation. It loads the
same packaged YAML definitions and domain node registrations used by the ACA
Native FastAPI host, then exposes a compiled **flat** graph via ``build_graph``.

Note:
  Agent Server persistence (threads/runs) is configured by the Agent Server
  process — not ``EDIM_CHECKPOINTER``. This entrypoint does not attach the
  FastAPI session router; use ACA Native for initialize/converse/regenerate.

Graph construction must remain free of network calls and user-specific credentials.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from edim_dde_ai.graph import build_graph
from edim_dde_ai.registry.agents import get_agent_definition
from edim_dde_domain.bootstrap import bootstrap_agents


@lru_cache(maxsize=16)
def _build_agent_graph(agent_id: str):
    """Load one packaged agent and compile its flat-state graph (cached)."""
    bootstrap_agents(load_external=False)
    return build_graph(get_agent_definition(agent_id))


def cluster_tuning_graph(_config: dict[str, Any] | None = None):
    """Return the compiled ``cluster_tuning`` graph for Agent Server.

    The optional config argument matches the LangGraph graph-factory contract.
    Profile selection is intentionally not request-controlled for this pilot:
    the graph id and packaged YAML are the approved deployment boundary.
    """
    return _build_agent_graph("cluster_tuning")


__all__ = ["cluster_tuning_graph"]
