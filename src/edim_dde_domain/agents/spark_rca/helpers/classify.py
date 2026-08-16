"""Rule-based Spark failure classification (LLM seed hint only).

Business purpose
----------------
Before the LLM diagnoses a job failure, this module produces a cheap
``classification_hint``::

    {\"category\": \"resource\", \"confidence\": 0.7, \"rationale\": \"...\"}

The hint seeds prompts and soft experience features. **It is not the product
root cause** — ``validate_rca_llm_output`` / the LLM still own diagnosis.

Extensibility
-------------
Signal groups (regex patterns → category) live in ``spark_rca.agent.yaml`` on
the ``domain.rca.classify_failure`` node (``signal_groups``). Adding a new
failure signature is usually a YAML change, not a Python change.

Structured SQL error events in ``raw_anchors.sql_errors`` short-circuit to
``sql_error`` without needing a regex match.

Public API
----------
* ``RCA_CATEGORIES`` — closed set allowed in API / evaluator contract
* ``classify_failure_pack`` — main entry used by ``logic.classify_failure``
"""

from __future__ import annotations

from typing import Any

# Closed product taxonomy for API contract + evaluator. Do not use this list as
# the sole retrieval vocabulary for the experience index (see experience_transform).
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
    """Flatten anchors + evidence excerpts into one searchable text blob.

    Args:
        evidence_pack: Assembled or client-supplied evidence pack.

    Returns:
        Newline-joined failure reasons, exception messages, and excerpts.
        Optional request ``_error_text`` (injected by ``logic.classify_failure``)
        is included when present.
    """
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
    # Optional free-text from the request (never persisted on the pack itself).
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
    require classifier code changes. Group order expresses precedence (first
    match wins after the structured SQL short-circuit).

    Args:
        evidence_pack: Evidence pack (may include ephemeral ``_error_text``).
        signal_groups: Ordered list of dicts from YAML, each roughly::

            {
              \"category\": \"resource\",
              \"confidence\": 0.7,
              \"rationale\": \"OOM / spill signals\",
              \"patterns\": [\"OutOfMemoryError\", \"Java heap space\"],
            }

    Returns:
        Hint dict with ``category``, ``confidence``, ``rationale``, and optionally
        ``matched_signal`` (truncated matched substring).

    Example:
        >>> classify_failure_pack(
        ...     {\"raw_anchors\": {\"sql_errors\": [{\"failure_reason\": \"TABLE_OR_VIEW_NOT_FOUND\"}]}},
        ... )
        {'category': 'sql_error', 'confidence': 0.75, ...}
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
            # Ignore misconfigured YAML categories rather than poisoning the hint.
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
                # Bad YAML regex — skip this pattern, keep classifying.
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
