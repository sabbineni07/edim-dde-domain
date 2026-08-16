---
name: document-python-module
description: Add engineer-oriented module header and API docstrings without changing behavior
agent: agent
argument-hint: Path to the .py file or package to document
---

# Document a Python module

Documentation only — **no behavior changes**.

1. Module docstring: Business purpose, pipeline fit, Public API
2. Public APIs: Args, Returns, Examples when helpful
3. Inline comments only for non-obvious rules (citation allowlists, acceptance gates, PII egress)

Match style in `agents/spark_rca/` and `agents/cluster_tuning/`.
