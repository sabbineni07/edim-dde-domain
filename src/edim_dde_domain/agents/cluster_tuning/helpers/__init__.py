"""Agent-local helpers for Cluster Tuning (rules/data; not LangGraph nodes).

Modules
-------
* ``sizing_policy`` — resource-pressure dimensions, sizing hints, reason codes
* ``guardrails`` — clamp LLM sizing JSON + retry feedback
* ``sku_allowlist`` — map family/vCPU intent onto allowed Azure SKUs
* ``validate_performance`` — peak-load fitness check (no LLM)
* ``resource_optimization`` — capacity comparison (vCPU × workers, no dollars)
* ``historical_context`` — experience + same-job shelf + guidance RAG text
* ``experience_transform`` — RecommendationStore → ``cluster-tuning-outcomes``

Node factories live in ``../nodes.py``; orchestration logic in ``../logic.py``.
"""
