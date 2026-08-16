"""Shared IO helpers (SQL). Agent-specific logic lives under ``agents/``.

Business purpose
----------------
Package marker for cross-agent tools. Import SQL helpers from
``edim_dde_domain.tools.sql`` (or via this package as it grows).

Public API
----------
* Submodule ``sql`` — named-param binding + Databricks execute
"""
