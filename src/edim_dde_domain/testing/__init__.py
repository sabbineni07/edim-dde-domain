"""Test-only helpers (not used by production runtime).

Business purpose
----------------
Offline LLM stand-ins and related fixtures so domain / API tests run without
Foundry. Import from ``edim_dde_domain.testing`` in pytest only.

Public API
----------
* ``DomainStubLLM`` — deterministic fake ``LLMProvider``
"""

from edim_dde_domain.testing.llm_stub import DomainStubLLM

__all__ = ["DomainStubLLM"]
