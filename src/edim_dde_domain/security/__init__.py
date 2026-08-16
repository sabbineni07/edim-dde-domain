"""Security helpers (PII redaction, Azure Key Vault bootstrap).

Business purpose
----------------
Shared privacy and secret-injection utilities used by hosts and agents —
not agent-specific. Re-exports the stable surface from ``pii`` and ``keyvault``.

Public API
----------
* ``PiiPattern`` / ``register_pii_pattern`` / ``clear_extra_pii_patterns`` /
  ``list_pii_patterns`` / ``redact_text`` / ``redact_value``
* ``load_key_vault_secrets``
"""

from edim_dde_domain.security.keyvault import load_key_vault_secrets
from edim_dde_domain.security.pii import (
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
    "load_key_vault_secrets",
    "redact_text",
    "redact_value",
    "register_pii_pattern",
]
