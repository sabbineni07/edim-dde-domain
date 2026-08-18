"""Bundled agents omit ``bindings`` by default; optional overlays still work."""

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

_ENV_REF_BINDINGS = {
    "llm": {
        "endpoint": "${ENV:EDIM_TEST_FOUNDRY_ENDPOINT}",
        "deployment": "${ENV:EDIM_TEST_FOUNDRY_DEPLOYMENT}",
        "temperature": 0.0,
        "top_p": 1.0,
        "top_k": 40,
        "max_tokens": 4096,
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
    """Shipped YAML keeps bindings commented; llm_chain uses process globals."""
    data = _load(path)
    assert "bindings" not in data
    validate_agent_dict(data)
    validate_agent_dict(data, use_jsonschema=True)

    defn = parse_agent_definition(data)
    assert defn.bindings is None
    captured = _capture_llm_chain_configs(defn)
    if not captured:
        pytest.skip(f"{path.name} has no llm_chain nodes")
    for cfg in captured.values():
        assert "endpoint" not in cfg
        assert "deployment" not in cfg
        assert "temperature" not in cfg
        assert "top_p" not in cfg
        assert "top_k" not in cfg
        assert "max_tokens" not in cfg


@pytest.mark.parametrize("path", _BUNDLED, ids=[p.name for p in _BUNDLED])
def test_bundled_agents_accept_env_ref_llm_override(
    path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Overlaying bindings.llm validates and injects into llm_chain config."""
    monkeypatch.setenv("EDIM_TEST_FOUNDRY_ENDPOINT", "https://bound.example.com")
    monkeypatch.setenv("EDIM_TEST_FOUNDRY_DEPLOYMENT", "bound-deployment")

    data = _load(path)
    data["bindings"] = copy.deepcopy(_ENV_REF_BINDINGS)
    validate_agent_dict(data)
    validate_agent_dict(data, use_jsonschema=True)

    defn = parse_agent_definition(data)
    captured = _capture_llm_chain_configs(defn)
    if not captured:
        pytest.skip(f"{path.name} has no llm_chain nodes")
    for cfg in captured.values():
        assert cfg["endpoint"] == "https://bound.example.com"
        assert cfg["deployment"] == "bound-deployment"
        assert cfg["temperature"] == 0.0
        assert cfg["max_tokens"] == 4096


@pytest.mark.parametrize("path", _BUNDLED, ids=[p.name for p in _BUNDLED])
def test_bundled_agents_fail_closed_on_missing_env(path: Path) -> None:
    """A declared ${ENV:…} with no value must stop graph build, not fall back."""
    data = _load(path)
    data["bindings"] = {
        "llm": {
            "endpoint": "${ENV:EDIM_TEST_FOUNDRY_ENDPOINT}",
            "deployment": "${ENV:EDIM_TEST_FOUNDRY_DEPLOYMENT}",
        }
    }
    defn = parse_agent_definition(data)
    if not _has_llm_chain(defn):
        pytest.skip("agent has no llm_chain node")
    with pytest.raises(EnvRefError):
        _capture_llm_chain_configs(defn)


def _has_llm_chain(definition) -> bool:
    return any(node.type == "llm_chain" for node in definition.nodes)
