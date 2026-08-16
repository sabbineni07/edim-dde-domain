---
description: Python conventions for edim-dde-domain agents and helpers
applyTo: "**/*.py"
---

# Python in edim-dde-domain

- `nodes.py`: thin factories only — close over YAML config; call `logic.*`.
- `logic.py`: pure state → patch; no FastAPI; fail soft for secondary context.
- `helpers/`: no IO when avoidable; document Business purpose on each module.
- Experience features: open/structural — do not make closed scenario enums the primary retrieval vocabulary.
- Citations: only refs/URLs present in evidence_pack or provider hits.
- Web egress: sanitized tokens only; never raw logs, SQL, paths, or IDs.
- Evaluators: deterministic; do not replace model confidence with evaluator confidence.
- Register new nodes/transforms/evaluators via bootstrap import paths.
