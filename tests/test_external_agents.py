"""Tests for external agent plugin loading."""

from __future__ import annotations

from pathlib import Path

import pytest
from edim_dde_ai import create_agent, list_agents
from edim_dde_ai.registry.agents import clear_agent_registry

from edim_dde_domain import bootstrap_agents, load_external_agents, reset_bootstrap
from edim_dde_domain.errors import DomainToolError
from edim_dde_domain.sources import clear_sources


@pytest.fixture(autouse=True)
def _clean_registries():
    clear_sources()
    reset_bootstrap()
    clear_agent_registry()
    yield
    reset_bootstrap()
    clear_agent_registry()
    clear_sources()


def _write_ext_agent_with_custom_node(root: Path) -> Path:
    pkg = root / "ext_demo"
    pkg.mkdir(parents=True)
    (pkg / "ext_demo.agent.yaml").write_text(
        """
agent_id: ext_demo
version: 1
entry: {method: invoke, sync: true}
graph:
  entry: mark
  nodes:
    - id: mark
      type: domain.ext.mark
    - id: done
      type: echo_result
      from_fields: [ext_flag]
  edges:
    - [mark, done]
    - [done, END]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (pkg / "nodes.py").write_text(
        """
from __future__ import annotations
from typing import Any
from edim_dde_ai import register_node

@register_node("domain.ext.mark")
def mark_factory(_config: dict[str, Any]):
    def _node(_state: dict[str, Any]) -> dict[str, Any]:
        return {"ext_flag": "from_external"}
    return _node
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return root


def _write_ext_agent_builtins_only(root: Path) -> Path:
    """YAML-only external agent (no custom node types) for bootstrap env tests."""
    pkg = root / "ext_env"
    pkg.mkdir(parents=True)
    (pkg / "ext_env.agent.yaml").write_text(
        """
agent_id: ext_env
version: 1
entry: {method: invoke, sync: true}
graph:
  entry: a
  nodes:
    - id: a
      type: set_value
      field: hello
      value: world
  edges:
    - [a, END]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return root


def test_load_external_agents_from_dir(tmp_path: Path):
    root = _write_ext_agent_with_custom_node(tmp_path)
    ids = load_external_agents([root], entry_points=False)
    assert "ext_demo" in ids
    out = create_agent("ext_demo").invoke({})
    assert out["result"]["ext_flag"] == "from_external"


def test_bootstrap_loads_EDIM_AGENT_DIRS(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = _write_ext_agent_builtins_only(tmp_path)
    monkeypatch.setenv("EDIM_AGENT_DIRS", str(root))
    bootstrap_agents()
    assert "cluster_tuning" in list_agents()
    assert "spark_rca" in list_agents()
    assert "ext_env" in list_agents()


def test_load_external_agents_missing_dir():
    with pytest.raises(DomainToolError, match="does not exist"):
        load_external_agents(["/no/such/edim-agents-dir"], entry_points=False)
