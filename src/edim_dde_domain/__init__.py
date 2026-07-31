"""EDIM DDE domain — tools + YAML agents (depends on edim-dde-ai)."""

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
