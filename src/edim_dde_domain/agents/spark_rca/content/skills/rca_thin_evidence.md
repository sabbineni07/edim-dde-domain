# Thin evidence

## Thin evidence / early failure

When timeline is mostly pipeline_start, stages are skipped, or metrics show little work before failure:
- Treat as possible **pre-execution / bootstrap** failure (config load, table init, permissions, upstream dependency).
- Still emit contributing_factors and recommended_actions as **low-confidence investigatory checks**.
- Examples of allowed checks: inspect full failure_reason/stack; confirm task_key and cluster logs around start; verify required configs/secrets; check whether failure occurs before Spark jobs are scheduled.
- Do not fabricate schema diffs or column lists unless those details already appear in the pack text.