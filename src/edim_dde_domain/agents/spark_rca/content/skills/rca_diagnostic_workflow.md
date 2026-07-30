# Diagnostic workflow

## Diagnostic workflow

Work in order; skip a step only when that signal type is absent from the pack.

1. **Failure signals & stacks** — Identify primary exception / failure_reason / error_type.
2. **Metric anomalies** — Look for failed tasks, spill, shuffle extremes, skipped vs failed stages.
3. **SQL / physical plan** — If plan or sql_text exists, note inefficient operators (e.g. Cartesian/NestedLoop, unbounded explode/window, unpruned scans) only when visible in the pack.
4. **Synthesis** — One primary category; factors that support it; actions that an engineer can take next.

When steps 2–3 are empty but step 1 has a clear error message, still produce actions based on that message with lower confidence.