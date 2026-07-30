# Plan operators

## RULE: Physical plan / operator diagnostics (incl. Cartesian)

Use only operators and SQL present in the evidence pack (`sql_text`, `physical_plan`, `logical_plan`, `join_types`, shuffle attrs).

### Unintended Cartesian / nested-loop joins
- **Signal:** `CartesianProductExec` or `NestedLoopJoinExec` in physical plan, especially with output rows exploding vs inputs.
- **Diagnostic:** Missing join condition or explicit `CROSS JOIN` on large datasets.
- **Fix:** Correct join predicates; replace cross join with keyed join; broadcast only if one side is small per evidence.
- Prefer category `sql_error` when this is the failure driver.

### Other plan anti-patterns
- **Explode / unbounded window** — row multiplication; constrain window frames or filter before explode.
- **Un-pruned / huge scans** — verify partition filters / predicate pushdown appear in SQL/plan text.
- Infer query rewrites from visible SQL/plan only — never invent table or column names absent from the pack.
- Put rewrite suggestions in `recommendations.code_query_rewrites`.