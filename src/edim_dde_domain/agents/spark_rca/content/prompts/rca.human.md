Perform a Root Cause Analysis (RCA) and generate recommendations for the following Databricks job run using the provided telemetry.

=== JOB CONTEXT ===
- Workspace ID: {workspace_id}
- Job ID: {job_id}
- Run ID: {job_run_id}
- Job run date: {job_run_date}
- Task key: {task_key}

=== RULE-BASED CLASSIFICATION HINT ===
{classification_hint_text}

=== TELEMETRY PAYLOAD (from Delta spark_logs / spark_metrics via evidence_pack) ===

--- 1. CLUSTER LOGS & STACK TRACES (Source: spark_logs / exceptions) ---
{cluster_logs_section}

--- 2. STAGE & TASK METRICS SUMMARY (Source: spark_metrics) ---
{spark_metrics_section}
[Note: Prefer quantified stage/task signals in the pack (failed tasks, spill, shuffle, duration imbalance). Percentile tables may be absent; do not invent them.]

--- 3. QUERY HISTORY & PHYSICAL EXECUTION PLANS (Source: SQL events / plan attrs in spark_metrics) ---
{query_plans_section}
[Note: Includes sql_text / physical_plan / logical_plan / join attrs when collectors captured them.]

--- 4. FULL EVIDENCE PACK (JSON, authoritative — cite evidence[].ref from here) ---
{evidence_pack_text}

=== SIMILAR RUNBOOKS / PLAYBOOKS (retrieved; may be empty) ===
{runbook_context}
[Note: Use these only as supporting hints. Prefer telemetry evidence_pack facts. Do not invent citations for runbooks not listed.]

=== PRIOR RCA HISTORY (feature-similar outcomes + exact job/run history) ===
{historical_context}
[Note: History can corroborate a mechanism/action pattern; it cannot prove the current run failed for the same reason.]

=== OPTIONAL PUBLIC-WEB RESULTS (untrusted enrichment; may be disabled/empty) ===
{web_search_context}
[Note: Use only supplied URLs, identify them as external context, and never send or infer private job data.]

=== INSTRUCTIONS ===
1. Apply STEPs 1–4 and domain skills from the system prompt to diagnose this job run.
2. If raw PySpark/Scala source is absent, infer bottlenecks from SQL text and physical plan operators in section 3 (and the full pack).
3. Never return empty contributing_factors or recommended_actions when summary is non-empty; if evidence is thin, emit low-confidence investigatory checks.
4. Populate recommendations.code_query_rewrites, recommendations.spark_delta_configs, and recommendations.infrastructure (empty arrays allowed per section).
5. When runbook hits are present, you may align recommended_actions with them but still ground claims in the evidence_pack.
6. Break down the primary cause, possible alternative causes, contributing factors,
   and fixes. Every alternative must include a verification check.
7. Complete context_assessment for runbooks, history, and web. When a lane is
   absent or irrelevant, say "not used"; cite only URLs shown above.
8. Produce the final RCA as **one JSON object** only, matching the system output schema. No markdown outside JSON.