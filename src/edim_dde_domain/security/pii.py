"""Compatibility re-export — implementation lives in ``edim_dde_ai.security``."""

from edim_dde_ai.security.pii import (
    PiiPattern,
    clear_extra_pii_patterns,
    list_pii_patterns,
    redact_text,
    redact_value,
    register_pii_pattern,
)

__all__ = [
    "PiiPattern",
    "clear_extra_pii_patterns",
    "list_pii_patterns",
    "redact_text",
    "redact_value",
    "register_pii_pattern",
]
