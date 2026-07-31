"""Spark RCA analysis + evidence assembly (SQL collect is domain.sql.query)."""

from __future__ import annotations

from typing import Any

from edim_dde_domain.llm.json_util import dumps, parse_json_object
from edim_dde_domain.tools.evidence_pack import build_evidence_pack


def assemble_evidence(state: dict[str, Any]) -> dict[str, Any]:
    """Build evidence_pack from SQL section outputs (or keep override/stub)."""
    existing = state.get("evidence_pack")
    if isinstance(existing, dict) and existing:
        return {}

    pack = build_evidence_pack(
        job_run_id=str(state.get("job_run_id") or "unknown-run"),
        job_id=state.get("job_id"),
        job_run_date=state.get("job_run_date"),
        task_key=state.get("task_key"),
        workspace_id=state.get("workspace_id"),
        failure_anchors=list(state.get("failure_anchors") or []),
        stage_pressure=list(state.get("stage_pressure") or []),
        error_logs=list(state.get("error_logs") or []),
        timeline=list(state.get("timeline_events") or []),
        sql_plans=list(state.get("sql_plans") or []),
    )
    return {"evidence_pack": pack}


def classify_failure(state: dict[str, Any]) -> dict[str, Any]:
    """Rule-based category from evidence text."""
    pack = state.get("evidence_pack") or {}
    text = " ".join(
        [
            str((pack.get("raw_anchors") or {}).get("failure_reason") or ""),
            " ".join(str(e.get("excerpt") or "") for e in (pack.get("evidence") or [])),
        ]
    ).lower()

    if any(k in text for k in ("oom", "out of memory", "heap space")):
        category, confidence = "resource", 0.85
    elif any(k in text for k in ("table not found", "analysisexception", "sql")):
        category, confidence = "sql_error", 0.8
    elif any(k in text for k in ("timeout", "cancelled")):
        category, confidence = "timeout_or_cancel", 0.7
    else:
        category, confidence = "unknown", 0.4

    return {
        "classification_hint": {
            "category": category,
            "confidence": confidence,
            "rationale": f"Matched keywords in evidence → {category}",
        }
    }


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

    def _s(value: Any) -> str:
        return "(not provided)" if value is None or value == "" else str(value)

    return {
        "workspace_id": _s(state.get("workspace_id") or pack.get("workspace_id")),
        "job_id": _s(state.get("job_id") or pack.get("job_id")),
        "job_run_id": _s(state.get("job_run_id") or pack.get("job_run_id")),
        "job_run_date": _s(state.get("job_run_date") or pack.get("job_run_date")),
        "task_key": _s(state.get("task_key") or pack.get("task_key")),
        "classification_hint": dumps(hint) if hint else "(none)",
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
        "evidence_pack": dumps(pack),
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
    """Clamp draft into a stable API response shape."""
    raw = state.get("llm_raw") or {}
    if not isinstance(raw, dict):
        raw = parse_json_object(raw)
    hint = state.get("classification_hint") or {}
    category = str(raw.get("category") or hint.get("category") or "unknown")
    confidence = float(raw.get("confidence") or hint.get("confidence") or 0.4)
    confidence = max(0.0, min(1.0, confidence))

    result = {
        "job_id": state.get("job_id"),
        "job_run_id": state.get("job_run_id"),
        "status": "completed",
        "root_cause": {
            "category": category,
            "summary": str(raw.get("summary") or "Unable to determine root cause"),
            "confidence": confidence,
        },
        "recommended_actions": list(raw.get("recommended_actions") or [])[:5],
        "classification_hint": hint,
        "evidence_pack": state.get("evidence_pack"),
    }
    return {"result": result}
