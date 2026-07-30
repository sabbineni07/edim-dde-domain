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

## Instruction
Output one JSON object with keys: pattern_analysis, node_family, vcpus, min_workers, max_workers, auto_termination_minutes, rationale. Set auto_termination_minutes to 0. No markdown outside JSON.
