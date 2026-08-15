# Diagnostic workflow

## Diagnostic workflow

Work in order; skip a step only when that signal type is absent from the pack.

1. **Failure signals & stacks** — Identify primary exception / failure_reason / error_type.
2. **Metric anomalies** — Look for failed tasks, spill, shuffle extremes, skipped vs failed stages.
3. **SQL / physical plan** — If plan or sql_text exists, note inefficient operators (e.g. Cartesian/NestedLoop, unbounded explode/window, unpruned scans) only when visible in the pack.
4. **Competing hypotheses** — Name plausible alternatives only when the pack
   supports them. For each alternative, provide a check that would confirm or reject it.
5. **Synthesis** — One primary mechanism and broad API category; separate
   contributing factors; actions that an engineer can take next.
6. **Context assessment** — Compare runbooks, prior outcomes, and optional web
   results with current-run evidence. Context corroborates; it does not create facts.

When steps 2–3 are empty but step 1 has a clear error message, still produce actions based on that message with lower confidence.

Do not force an unfamiliar failure into a familiar story. Use category `unknown`,
preserve the specific signature, and recommend discriminating checks when the
mechanism is not supported.