# SQL analysis, resolution, and planning failures

SQL failures that occur before task execution commonly expose an exception
class and an unresolved identifier, incompatible expression, parse location, or
unsupported operation. Treat the observed exception and SQL/plan attributes as
the evidence; do not infer missing source code.

## Diagnostic method

1. Identify whether parsing, name resolution, type checking, or execution failed.
2. Capture the unresolved catalog/schema/table/column or expression only when it
   appears in the evidence pack.
3. Check whether a physical plan exists. Its absence may support a pre-execution
   analysis failure but does not identify the missing object by itself.
4. Separate a missing object from a permission failure; both can look like an
   inaccessible table, but require different verification.

## Actions

- Fully qualify identifiers and verify the active catalog/schema.
- Compare the deployed schema with the query's expected columns and types.
- Validate the executing principal's visibility separately from object existence.
- Re-run `EXPLAIN` or the smallest failing expression after correction.

Keywords: AnalysisException, ParseException, unresolved identifier, cannot
resolve, table not found, column not found, SQLSTATE, query plan.
