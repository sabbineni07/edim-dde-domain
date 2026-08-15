# RCA action quality

Recommendations must be actionable, evidence-bounded, and ordered:

1. Give the immediate containment or recovery action when justified.
2. Give the durable code/query/configuration fix.
3. Give a verification step and the signal expected after the fix.
4. Distinguish a recommended change from an investigatory check.

Do not emit unexplained settings or exact numeric values unless the evidence or
a supplied runbook supports them. Do not recommend simultaneous code, Spark
configuration, and infrastructure changes merely to fill every output array.
Empty grouped arrays are valid when that type of change is not supported.

When evidence is thin, recommend discriminating checks such as collecting the
missing executor stack, stage percentile metrics, plan operator, permissions
audit, or storage/network error. Do not disguise investigation as a confirmed fix.
