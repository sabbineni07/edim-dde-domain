"""Shared JSON / prompt payload helpers for LLM graph steps.

Business purpose
----------------
Agents need stable dicts from messy model output (fenced markdown, leading
prose, non-object JSON). Also a consistent pretty-dump for prompt payloads.

Public API
----------
* ``dumps`` — ``json.dumps`` with ``default=str`` and indent
* ``parse_json_object`` — coerce LLM text / dict into a ``dict`` (or ``{}``)
"""

from __future__ import annotations

import json
import re
from typing import Any


_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def dumps(value: Any) -> str:
    """Serialize ``value`` for prompt inclusion (``default=str``, indented).

    Args:
        value: Any JSON-ish structure (datetimes become strings via ``default``).

    Returns:
        Pretty-printed JSON string.
    """
    return json.dumps(value, default=str, indent=2)


def parse_json_object(raw: Any) -> dict[str, Any]:
    """Parse LLM output into a dict (handles fenced markdown).

    Tries, in order: already-a-dict, direct ``json.loads``, markdown-fenced
    JSON block, then outermost ``{...}`` substring. Non-object JSON becomes
    ``{}``.

    Args:
        raw: Model text, dict, or ``None``.

    Returns:
        A dict (possibly empty) — never raises on parse failure.

    Examples::

        parse_json_object('{"a": 1}')                    # → {"a": 1}
        parse_json_object('Here is JSON:\\n{\"ok\": true}')  # → {"ok": True}
    """
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
