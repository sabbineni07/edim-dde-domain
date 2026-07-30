## SKU allow-list (guardrails)

Recommended node types are validated server-side against an allow-list.

If the LLM proposes a SKU outside the allow-list, guardrails map to the nearest allowed family/vCPU combination.
Families supported: D, E, F, L with vCPUs 4–64.
