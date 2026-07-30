"""Shared pytest fixtures for edim-dde-domain."""

from __future__ import annotations

import pytest

from edim_dde_ai import set_llm_provider
from edim_dde_ai.content.registry import clear_llm_provider

from edim_dde_domain import bootstrap_agents, reset_bootstrap
from edim_dde_domain.sources import clear_sources

from llm_stub import DomainStubLLM


@pytest.fixture
def stub_llm():
    """Install a fake LLMProvider so llm_chain nodes can run offline."""
    set_llm_provider(DomainStubLLM())
    yield
    clear_llm_provider()


@pytest.fixture
def bootstrapped_agents(stub_llm):
    """Load sources + register domain agent YAMLs (requires stub_llm)."""
    clear_sources()
    reset_bootstrap()
    bootstrap_agents()
    yield
    reset_bootstrap()
    clear_llm_provider()
