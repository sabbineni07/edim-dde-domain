"""Spark RCA analysis + evidence assembly (SQL collect is domain.sql.query)."""

from __future__ import annotations

from typing import Any

from edim_dde_domain.agents.spark_rca.helpers.classify import classify_failure_pack
from edim_dde_domain.agents.spark_rca.helpers.evidence_pack import build_evidence_pack
from edim_dde_domain.agents.spark_rca.helpers.validate import validate_rca_llm_output
from edim_dde_domain.llm.json_util import dumps, parse_json_object


def _seed_from_rows(rows: list[Any], *keys: str) -> str | None:
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in keys:
            val = row.get(key)
            if val not in (None, ""):
                return str(val)
    return None


def assemble_evidence(state: dict[str, Any]) -> dict[str, Any]:
    """Build evidence_pack from SQL section outputs (or keep override/stub)."""
    existing = state.get("evidence_pack")
    if isinstance(existing, dict) and existing:
        return {}

    failure_anchors = list(state.get("failure_anchors") or [])
    sql_plans = list(state.get("sql_plans") or [])
    seed_rows = failure_anchors + sql_plans + list(state.get("timeline_events") or [])

    job_id = state.get("job_id") or _seed_from_rows(seed_rows, "job_id")
    job_run_date = state.get("job_run_date") or _seed_from_rows(
        seed_rows, "job_run_date"
    )
    task_key = state.get("task_key") or _seed_from_rows(seed_rows, "task_key")
    workspace_id = state.get("workspace_id") or _seed_from_rows(
        seed_rows, "workspace_id"
    )

    pack = build_evidence_pack(
        job_run_id=str(state.get("job_run_id") or "unknown-run"),
        job_id=job_id,
        job_run_date=job_run_date,
        task_key=task_key,
        workspace_id=workspace_id,
        failure_anchors=failure_anchors,
        stage_pressure=list(state.get("stage_pressure") or []),
        error_logs=list(state.get("error_logs") or []),
        timeline=list(state.get("timeline_events") or []),
        sql_plans=sql_plans,
    )
    out: dict[str, Any] = {"evidence_pack": pack}
    # Surface seeded ids onto state for API / later nodes
    if job_id and not state.get("job_id"):
        out["job_id"] = job_id
    if job_run_date and not state.get("job_run_date"):
        out["job_run_date"] = job_run_date
    if task_key and not state.get("task_key"):
        out["task_key"] = task_key
    return out


def classify_failure(state: dict[str, Any]) -> dict[str, Any]:
    """Rule-based category from evidence pack (legacy taxonomy)."""
    pack = state.get("evidence_pack") or {}
    if not isinstance(pack, dict):
        pack = {}
    # Include optional request error_text without mutating the pack permanently
    view = dict(pack)
    if state.get("error_text"):
        view["_error_text"] = state.get("error_text")
    return {"classification_hint": classify_failure_pack(view)}


def build_retrieval_query(state: dict[str, Any]) -> dict[str, Any]:
    """Build a free-text query for runbook similarity search (RAG pilot)."""
    pack = state.get("evidence_pack") or {}
    if not isinstance(pack, dict):
        pack = {}
    hint = state.get("classification_hint") or {}
    reason = str((pack.get("raw_anchors") or {}).get("failure_reason") or "")
    category = str(hint.get("category") or "")
    excerpts: list[str] = []
    for item in (pack.get("evidence") or [])[:5]:
        if isinstance(item, dict) and item.get("excerpt"):
            excerpts.append(str(item["excerpt"])[:400])
    parts = [p for p in [category, reason, *excerpts] if p and p.strip()]
    query = "\n".join(parts).strip() or category or "spark job failure"
    return {"retrieval_query": query}


def _section_text(section: Any, empty_message: str) -> str:
    if not section:
        return empty_message
    if isinstance(section, dict) and not any(section.values()):
        return empty_message
    return dumps(section)


def prepare_llm_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Flatten evidence + classification into RCA human-prompt string fields."""
    pack = state.get("evidence_pack") or {}
    if not isinstance(pack, dict):
        pack = {}
    sections = pack.get("sections") or {}
    hint = state.get("classification_hint") or {}
    runbook_context = state.get("runbook_context") or state.get("retrieval_context")

    def _s(value: Any) -> str:
        return "(not provided)" if value is None or value == "" else str(value)

    return {
        "workspace_id": _s(state.get("workspace_id") or pack.get("workspace_id")),
        "job_id": _s(state.get("job_id") or pack.get("job_id")),
        "job_run_id": _s(state.get("job_run_id") or pack.get("job_run_id")),
        "job_run_date": _s(state.get("job_run_date") or pack.get("job_run_date")),
        "task_key": _s(state.get("task_key") or pack.get("task_key")),
        # Non-colliding keys so dict classification_hint / evidence_pack stay intact
        "classification_hint_text": dumps(hint) if hint else "(none)",
        "cluster_logs_section": _section_text(
            sections.get("logs"),
            "(no ERROR/WARN/exception excerpts in this evidence_pack)",
        ),
        "spark_metrics_section": _section_text(
            sections.get("stage_metrics"),
            "(no stage/task metric excerpts in this evidence_pack)",
        ),
        "query_plans_section": _section_text(
            sections.get("sql_plans"),
            "(no sql_text/physical_plan/sql_error attrs in this evidence_pack)",
        ),
        "evidence_pack_text": dumps(pack),
        "runbook_context": _s(runbook_context)
        if runbook_context
        else "(no runbook hits retrieved — retrieval disabled or empty index)",
    }


def parse_llm_json(state: dict[str, Any]) -> dict[str, Any]:
    """Parse synthesize llm_chain text into llm_raw dict for validate_output."""
    parsed = parse_json_object(state.get("llm_raw"))
    if parsed:
        return {"llm_raw": parsed}
    # Soft fallback from classification when LLM returns non-JSON
    hint = state.get("classification_hint") or {}
    pack = state.get("evidence_pack") or {}
    reason = (pack.get("raw_anchors") or {}).get("failure_reason") or "failure"
    category = hint.get("category") or "unknown"
    return {
        "llm_raw": {
            "category": category,
            "summary": f"Likely {category}: {reason}",
            "confidence": float(hint.get("confidence") or 0.5),
            "recommended_actions": ["Re-run with additional logging"],
            "evidence_refs": [
                str(e.get("ref")) for e in (pack.get("evidence") or []) if e.get("ref")
            ],
        }
    }


def validate_output(state: dict[str, Any]) -> dict[str, Any]:
    """Clamp draft into a stable API response shape (legacy-rich fields retained)."""
    raw = state.get("llm_raw") or {}
    if not isinstance(raw, dict):
        raw = parse_json_object(raw) or {}
    hint = state.get("classification_hint") or {}
    if not isinstance(hint, dict):
        hint = {}
    pack = state.get("evidence_pack") or {}
    if not isinstance(pack, dict):
        pack = {}

    validated = validate_rca_llm_output(
        raw, evidence_pack=pack, classification_hint=hint
    )
    result = {
        "request_id": state.get("request_id"),
        "job_id": state.get("job_id") or pack.get("job_id"),
        "job_run_id": state.get("job_run_id") or pack.get("job_run_id"),
        "task_key": state.get("task_key") or pack.get("task_key"),
        "status": "completed",
        "job_status": validated.get("job_status"),
        "root_cause": validated.get("root_cause"),
        "recommended_actions": validated.get("recommended_actions") or [],
        "contributing_factors": validated.get("contributing_factors") or [],
        "evidence_analysis": validated.get("evidence_analysis") or {},
        "recommendations": validated.get("recommendations") or {},
        "timeline": validated.get("timeline") or [],
        "evidence": validated.get("evidence") or [],
        "classification_hint": hint,
        "evidence_pack": pack,
    }
    return {"result": result}
