## Input: Current configuration
{current_config}

## Input: Job run ingest (this run only)
{job_run_ingest}

## Input: Sizing hints (pre-check)
{sizing_hints}

## Input: Guardrail feedback (retry only; otherwise None)
{guardrail_feedback}

## Input: Historical context (if any)
{historical_context}

## Decision procedure
1. Compare **this run's** measured pressure level across every resource dimension
   in sizing_hints; identify unknown/missing dimensions explicitly.
2. Choose worker family/vCPUs only from a supported limiting-resource shape.
   Do not turn utilization into a failure claim or change family merely because a
   similar case did.
3. Choose worker bounds from observed avg/p99 consumption and sizing_hints.
4. Review each historical section using the precedence rules. State which
   experience/guidance corroborated the decision, including `occurrences` when
   present, or explain why it was rejected.
5. Apply guardrail feedback exactly on a retry.

## Instruction
Output one JSON object with keys: pattern_analysis, node_family, vcpus,
min_workers, max_workers, auto_termination_minutes, rationale. Include all five
required pattern_analysis headings, including `### 5. Historical evidence`.
Set auto_termination_minutes to 0. No markdown outside JSON.
