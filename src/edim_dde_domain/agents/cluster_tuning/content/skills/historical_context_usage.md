# Using historical context safely

Historical context has three evidence types:

1. **Similar past experiences** — feature-similar pressure/action/outcome cards.
   Prefer `applied`, then `accepted`, then `proposed`. `occurrences=N` is useful
   corroboration. Match on measured dimensions, pressure levels, and limiting
   resource—not job id or a named scenario.
2. **Prior recommendations** — exact same-job history. Use for continuity and to
   avoid oscillation, but current metrics win if workload behavior changed.
3. **Retrieved sizing guidance** — general playbooks. Use for principles, not as
   proof that an action succeeded.

Required behavior:
- Live `job_run_ingest` outranks every historical source.
- Never copy a node family, vCPU tier, or worker count without matching current
  evidence.
- Do not average numeric configurations across unrelated experiences.
- Repeated actions (`occurrences > 1`) increase confidence only when their
  resource-pressure features match the current run.
- Mention relevant history—or explicitly say no relevant history—in
  `### 5. Historical evidence`.
