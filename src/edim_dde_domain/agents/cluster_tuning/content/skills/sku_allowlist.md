## SKU allow-list (guardrails)

Recommended node types are validated server-side against an allow-list.

If the LLM proposes a SKU outside the allow-list, guardrails map to the nearest allowed family/vCPU combination.
Families supported: D, E, F, L with vCPUs 4–64.

Do not rely on clamping as the decision mechanism:
- Produce a legal family/vCPU pair initially.
- Keep the current family unless live resource shape justifies a family move.
- When measured pressures are low and capacity headroom is high, first reduce
  max_workers or the vCPU tier; do not default to a family from a workload label.
- Treat a guardrail clamp as evidence that the proposal was invalid, not as
  confirmation that the clamped value is optimal.
