# Data skew / shuffle

## RULE: Data skew / shuffle imbalance

- **Signal:** Max task duration or shuffle read/write ≫ peer/median values when comparable figures exist in the pack (rule of thumb: >5x). Also FetchFailed or explicit skew language in logs.
- **Diagnostic:** Join or aggregation key concentrated on few values (NULL, default string, hot keys) when SQL text/plan is available.
- **Fix:** Skew hints (`/*+ SKEW('table', 'column') */`), salt join keys, filter default/NULL keys before joins, or repartition on a better key — only when supported by pack signals.
- If percentiles are missing, recommend verifying task duration/shuffle distribution in Spark UI and still emit investigatory actions.
- Map category toward `skew_shuffle` when this is the primary story.