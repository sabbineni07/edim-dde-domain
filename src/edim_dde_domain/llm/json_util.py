"""Shared JSON / prompt payload helpers for LLM graph steps."""

from __future__ import annotations

import json
import re
from typing import Any


_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def dumps(value: Any) -> str:
    return json.dumps(value, default=str, indent=2)


def parse_json_object(raw: Any) -> dict[str, Any]:
    """Parse LLM output into a dict (handles fenced markdown)."""
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return {}
    text = str(raw).strip()
    if not text:
        return {}
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        pass
    match = _FENCE_RE.search(text)
    if match:
        try:
            value = json.loads(match.group(1).strip())
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            value = json.loads(text[start : end + 1])
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}
