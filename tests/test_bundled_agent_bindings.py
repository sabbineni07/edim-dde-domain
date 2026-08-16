"""Bundled agents work with and without optional ``bindings.llm`` (Phase 1)."""

from __future__ import annotations

import copy
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

pytest.importorskip("jsonschema")

from edim_dde_ai.core.definition import parse_agent_definition
from edim_dde_ai.core.env_refs import EnvRefError
from edim_dde_ai.graph import builder as builder_mod
from edim_dde_ai.schema.validate import validate_agent_dict

_AGENTS_ROOT = (
    Path(__file__).resolve().parents[1] / "src" / "edim_dde_domain" / "agents"
)
_BUNDLED = sorted(_AGENTS_ROOT.rglob("*.agent.yaml"))

_BINDINGS = {
    "llm": {
        "endpoint": "${ENV:EDIM_TEST_FOUNDRY_ENDPOINT}",
        "deployment": "${ENV:EDIM_TEST_FOUNDRY_DEPLOYMENT}",
    }
}


def _load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _capture_llm_chain_configs(definition) -> dict[str, dict]:
    """Build nodes with stub factories, recording configs of llm_chain nodes."""
    captured: dict[str, dict] = {}

    def spy_factory(node_type: str):
        def factory(cfg: dict):
            if node_type == "llm_chain":
                captured[cfg.get("chain", cfg.get("agent_id", "?"))] = dict(cfg)
            return lambda state: {}

        return factory

    with patch.object(builder_mod, "get_node_factory", spy_factory):
        builder_mod.GraphBuilder(definition).add_nodes()
    return captured


@pytest.mark.parametrize("path", _BUNDLED, ids=[p.name for p in _BUNDLED])
def test_bundled_agents_ship_without_bindings(path: Path) -> None:
    """Shipped YAML must stay on process globals (no injected LLM target)."""
    data = _load(path)
    assert "bindings" not in data
    defn = parse_agent_definition(data)
    assert defn.bindings is None
    for cfg in _capture_llm_chain_configs(defn).values():
        assert "endpoint" not in cfg
        assert "deployment" not in cfg


@pytest.mark.parametrize("path", _BUNDLED, ids=[p.name for p in _BUNDLED])
def test_bundled_agents_accept_llm_bindings(
    path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adding bindings.llm validates and reaches every llm_chain node config."""
    monkeypatch.setenv("EDIM_TEST_FOUNDRY_ENDPOINT", "https://bound.example.com")
    monkeypatch.setenv("EDIM_TEST_FOUNDRY_DEPLOYMENT", "bound-deployment")

    data = _load(path)
    data["bindings"] = copy.deepcopy(_BINDINGS)
    validate_agent_dict(data)
    validate_agent_dict(data, use_jsonschema=True)

    defn = parse_agent_definition(data)
    captured = _capture_llm_chain_configs(defn)
    for cfg in captured.values():
        assert cfg["endpoint"] == "https://bound.example.com"
        assert cfg["deployment"] == "bound-deployment"


@pytest.mark.parametrize("path", _BUNDLED, ids=[p.name for p in _BUNDLED])
def test_bundled_agents_fail_closed_on_missing_env(path: Path) -> None:
    """A declared ${ENV:…} with no value must stop graph build, not fall back."""
    data = _load(path)
    data["bindings"] = copy.deepcopy(_BINDINGS)
    defn = parse_agent_definition(data)
    if not _has_llm_chain(defn):
        pytest.skip("agent has no llm_chain node")
    with pytest.raises(EnvRefError):
        _capture_llm_chain_configs(defn)


def _has_llm_chain(definition) -> bool:
    return any(node.type == "llm_chain" for node in definition.nodes)
