"""BL-002: bundled domain agents must satisfy R1 schema contract."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytest.importorskip("jsonschema")

from edim_dde_ai.core.definition import parse_agent_definition
from edim_dde_ai.schema.validate import validate_agent_dict

_AGENTS_ROOT = (
    Path(__file__).resolve().parents[1] / "src" / "edim_dde_domain" / "agents"
)
_BUNDLED = sorted(_AGENTS_ROOT.rglob("*.agent.yaml"))


@pytest.mark.parametrize(
    "path",
    _BUNDLED,
    ids=[p.name for p in _BUNDLED],
)
def test_bundled_agent_matches_schema(path: Path) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    validate_agent_dict(data)
    validate_agent_dict(data, use_jsonschema=True)
    # Structural graph parse must also succeed
    parse_agent_definition(data)
