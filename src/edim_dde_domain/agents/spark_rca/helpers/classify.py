"""Rule-based Spark failure classification for RCA seeding (legacy parity)."""

from __future__ import annotations

from typing import Any

RCA_CATEGORIES = (
    "sql_error",
    "data_quality",
    "resource",
    "skew_shuffle",
    "timeout_or_cancel",
    "config",
    "unknown",
)

def _text_blob(evidence_pack: dict[str, Any]) -> str:
    parts: list[str] = []
    anchors = evidence_pack.get("raw_anchors") or {}
    pe = anchors.get("pipeline_end") or {}
    if pe.get("failure_reason"):
        parts.append(str(pe["failure_reason"]))
    attrs = pe.get("attributes") or {}
    for k in ("error_type", "error_message"):
        if attrs.get(k):
            parts.append(str(attrs[k]))
    for err in anchors.get("sql_errors") or []:
        parts.append(str(err.get("failure_reason") or ""))
        a = err.get("attributes") or {}
        parts.append(str(a.get("error_type") or ""))
        parts.append(str(a.get("error_message") or ""))
    for exc in anchors.get("top_exceptions") or []:
        parts.append(str(exc.get("exception") or ""))
        parts.append(str(exc.get("message") or ""))
    for ev in evidence_pack.get("evidence") or []:
        parts.append(str(ev.get("excerpt") or ""))
    # Optional free-text from the request
    if evidence_pack.get("_error_text"):
        parts.append(str(evidence_pack["_error_text"]))
    return "\n".join(parts)


def classify_failure_pack(
    evidence_pack: dict[str, Any],
    *,
    signal_groups: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a configurable signal hint; the LLM still performs diagnosis.

    Pattern groups live in agent YAML so adding signatures/categories does not
    require classifier code changes. Group order expresses precedence.
    """
    import re

    anchors = evidence_pack.get("raw_anchors") or {}
    sql_errors: list[dict[str, Any]] = list(anchors.get("sql_errors") or [])
    blob = _text_blob(evidence_pack)

    # Structured SQL error events are direct evidence independent of text regex.
    if sql_errors:
        return {
            "category": "sql_error",
            "confidence": 0.75,
            "rationale": "Structured SQL failure events are present.",
        }

    for group in signal_groups or []:
        if not isinstance(group, dict):
            continue
        category = str(group.get("category") or "unknown").strip()
        if category not in RCA_CATEGORIES:
            continue
        patterns = [
            str(pattern).strip()
            for pattern in (group.get("patterns") or [])
            if str(pattern).strip()
        ]
        for pattern in patterns:
            try:
                matched = re.search(pattern, blob, re.IGNORECASE)
            except re.error:
                continue
            if matched:
                try:
                    confidence = float(group.get("confidence", 0.55))
                except (TypeError, ValueError):
                    confidence = 0.55
                return {
                    "category": category,
                    "confidence": max(0.0, min(1.0, confidence)),
                    "rationale": str(
                        group.get("rationale")
                        or f"Configured {category} signal pattern matched telemetry."
                    ),
                    "matched_signal": matched.group(0)[:160],
                }

    has_any = bool(
        anchors.get("pipeline_end")
        or sql_errors
        or anchors.get("top_exceptions")
        or evidence_pack.get("evidence")
    )
    return {
        "category": "unknown",
        "confidence": 0.35 if has_any else 0.1,
        "rationale": "Insufficient distinctive signals for a specific category.",
    }
