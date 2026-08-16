"""Agent-local helpers for Spark RCA (rules/data; not LangGraph nodes).

Modules
-------
* ``evidence_pack`` — assemble bounded pack from SQL collector rows
* ``classify`` — YAML-driven rule hint (LLM seed only)
* ``validate`` — clamp LLM JSON to API contract
* ``failure_signals`` — YAML attr extractors for experience ``signal_*`` labels
* ``experience_transform`` — RecommendationStore → ``spark-rca-outcomes`` cards
* ``historical_context`` — compose experience + same-job shelf for the prompt

Node factories live in ``../nodes.py``; orchestration logic in ``../logic.py``.
"""
