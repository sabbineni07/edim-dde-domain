"""Spark RCA agent package (Job Failure Root Cause Analysis).

Contains:
* ``spark_rca.agent.yaml`` — graph topology, SQL collectors, history/web knobs
* ``nodes.py`` — ``domain.rca.*`` LangGraph factories
* ``logic.py`` — pure business logic behind those nodes
* ``helpers/`` — evidence pack, classify, validate, experience, history
* ``content/`` — prompts, skills, runbooks
* ``knowledge/`` — curated spark-runbooks corpus files

Bootstrap registers nodes, the experience transform, and ``spark_rca.quality``.
HTTP entry: ``POST /api/v1/rca/analyze`` (edim-dde-api).
"""
