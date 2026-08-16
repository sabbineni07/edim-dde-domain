---
name: harden-agent-prompts
description: Improve prompts/skills/runbooks and validation without taxonomy lock-in
agent: agent
argument-hint: Which agent (cluster_tuning or spark_rca) and the quality gap
---

# Harden agent prompts and skills

- Prefer evidence-grounded instructions; forbid invented citations
- History / runbooks / web are **secondary**; say so in system+human prompts
- Add skills for workflow quality, not closed scenario laundry lists for retrieval
- Validate/clamp LLM JSON to contract; allowlist refs and web URLs
- Prefer YAML signal groups / pressure knobs over new hard-coded scenario enums
- Add or update deterministic `*.quality` evaluator dimensions when contract changes
- Update golden/unit tests and agent docs

Do not change framework packages unless a new node type is truly required.
