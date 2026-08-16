"""JSON helpers + Azure AI Foundry LLM provider.

Business purpose
----------------
Shared LLM utilities for agent graph steps: Foundry chat completions adapter
for edim-dde-ai ``llm_chain``, plus robust JSON extraction from model text.

Public API
----------
* ``FoundryLLMNotConfiguredError`` / ``FoundryLLMProvider``
* ``get_foundry_access_token`` / ``get_foundry_llm_provider`` /
  ``clear_foundry_llm_provider_cache``
* ``dumps`` / ``parse_json_object``
"""

from edim_dde_domain.llm.foundry import (
    FoundryLLMNotConfiguredError,
    FoundryLLMProvider,
    clear_foundry_llm_provider_cache,
    get_foundry_access_token,
    get_foundry_llm_provider,
)
from edim_dde_domain.llm.json_util import dumps, parse_json_object

__all__ = [
    "FoundryLLMNotConfiguredError",
    "FoundryLLMProvider",
    "clear_foundry_llm_provider_cache",
    "dumps",
    "get_foundry_access_token",
    "get_foundry_llm_provider",
    "parse_json_object",
]
