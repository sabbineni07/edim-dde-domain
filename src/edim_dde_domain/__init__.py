"""EDIM DDE domain package — tools, sources, and YAML agents on edim-dde-ai.

Business purpose
----------------
Product-facing domain layer that sits on ``edim-dde-ai``: Databricks SQL
sources, Foundry LLM wiring, shared security helpers, and agent bootstrap.
Hosts (``edim-dde-api``) import bootstrap / errors from here at startup.

Public API
----------
* ``__version__`` — package version string
* ``bootstrap_agents`` / ``load_external_agents`` / ``reset_bootstrap``
* ``DomainToolError`` / ``DatabricksNotConfiguredError`` / ``NoJobMetricsError``
* ``FoundryLLMNotConfiguredError``
"""

from edim_dde_domain.bootstrap import (
    bootstrap_agents,
    load_external_agents,
    reset_bootstrap,
)
from edim_dde_domain.errors import (
    DatabricksNotConfiguredError,
    DomainToolError,
    NoJobMetricsError,
)
from edim_dde_domain.llm import FoundryLLMNotConfiguredError

__version__ = "0.1.0"
__all__ = [
    "__version__",
    "bootstrap_agents",
    "load_external_agents",
    "reset_bootstrap",
    "DatabricksNotConfiguredError",
    "DomainToolError",
    "FoundryLLMNotConfiguredError",
    "NoJobMetricsError",
]
