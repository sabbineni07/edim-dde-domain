"""Expandable PII redaction patterns (BL-014).

Business purpose
----------------
Deterministic string/structure redaction for logs, evidence packs, and
LLM prompts. Ships FinTech baseline patterns (SSN, PAN-like cards, labeled
account / member ids); orgs can register extras at runtime.

Public API
----------
* ``PiiPattern`` — named compiled regex + replacement
* ``register_pii_pattern`` / ``clear_extra_pii_patterns`` / ``list_pii_patterns``
* ``redact_text`` — redact a single string
* ``redact_value`` — recursively redact strings in dict/list/tuple trees
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class PiiPattern:
    """One named redaction rule.

    Attributes:
        name: Short label used in default ``[REDACTED:name]`` replacements.
        regex: Compiled pattern applied with ``sub``.
        replacement: Optional custom replacement; default uses the name.
    """

    name: str
    regex: re.Pattern[str]
    replacement: str | None = None

    def replace(self, text: str) -> str:
        """Apply this pattern to ``text`` and return the redacted string."""
        repl = self.replacement or f"[REDACTED:{self.name}]"
        return self.regex.sub(repl, text)


# FinTech baseline — extend this list over time; keep unit tests in sync.
_DEFAULT_PATTERNS: tuple[PiiPattern, ...] = (
    PiiPattern(
        name="ssn",
        regex=re.compile(
            r"\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b"
        ),
    ),
    PiiPattern(
        name="credit_card",
        # Grouped PAN-like (xxxx-xxxx-xxxx-xxxx); avoids bare telemetry integers.
        regex=re.compile(r"\b(?:\d{4}[ -]){3}\d{1,4}\b"),
    ),
    PiiPattern(
        name="account_number",
        regex=re.compile(
            r"\b(?:account\s*(?:number|no\.?|#)?|acct\.?#?)\s*[:#-]?\s*[A-Za-z0-9-]{4,}\b",
            re.IGNORECASE,
        ),
    ),
    PiiPattern(
        name="member_id",
        regex=re.compile(
            r"\b(?:member\s*(?:id|number|no\.?|#)?|memberid|member#)\s*[:#-]?\s*[A-Za-z0-9-]{3,}\b",
            re.IGNORECASE,
        ),
    ),
)

_EXTRA: list[PiiPattern] = []


def register_pii_pattern(pattern: PiiPattern) -> None:
    """Append a custom pattern (tests / org extensions).

    Args:
        pattern: Frozen ``PiiPattern`` to apply after the defaults.
    """
    _EXTRA.append(pattern)


def clear_extra_pii_patterns() -> None:
    """Remove all runtime-registered extra patterns (test cleanup)."""
    _EXTRA.clear()


def list_pii_patterns() -> list[PiiPattern]:
    """Return defaults followed by any registered extras."""
    return list(_DEFAULT_PATTERNS) + list(_EXTRA)


def redact_text(text: str, patterns: Iterable[PiiPattern] | None = None) -> str:
    """Apply PII patterns to a string in registration order.

    Args:
        text: Input text (empty string returned unchanged).
        patterns: Optional override list; default ``list_pii_patterns()``.

    Returns:
        Redacted string.
    """
    if not text:
        return text
    out = text
    for pat in patterns or list_pii_patterns():
        out = pat.replace(out)
    return out


def redact_value(value: Any, patterns: Iterable[PiiPattern] | None = None) -> Any:
    """Recursively redact strings in dict/list/tuple structures.

    Non-container, non-string values are returned unchanged.

    Args:
        value: Arbitrary nested structure.
        patterns: Optional override pattern list.

    Returns:
        Structure of the same shape with strings redacted.
    """
    if isinstance(value, str):
        return redact_text(value, patterns)
    if isinstance(value, dict):
        return {k: redact_value(v, patterns) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(v, patterns) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_value(v, patterns) for v in value)
    return value
