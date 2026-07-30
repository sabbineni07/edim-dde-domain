# Delta concurrency

## RULE: Delta concurrency conflict

- **Signal:** `ConcurrentAppendException`, `ConcurrentTransactionException`, or similar conflict text in failure_reason / logs.
- **Diagnostic:** Multiple jobs concurrently appending or updating overlapping partitions/files in a Delta table.
- **Fix:** Exponential backoff retries; isolate writers by disjoint partition/keys; consider Liquid Clustering / layout changes when evidence supports write conflicts on the same paths.
- Put retry/isolation guidance in `recommended_actions` / `recommendations.infrastructure`; keep confidence proportional to how explicit the exception text is.
- Prefer category `config` (or `unknown` if conflict text is ambiguous).