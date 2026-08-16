"""Normalize / clamp Spark RCA LLM JSON into the stable API contract.

Business purpose
----------------
The synthesize step returns free-form JSON. This module:

* Maps messy categories onto ``RCA_CATEGORIES`` (aliases + hint fallback)
* Clamps confidence and derives High/Medium/Low labels
* Filters ``evidence_refs`` and web citations to **allowlisted** values from
  the live evidence pack / web-search hits (no hallucinated citations)
* Fills missing summary / actions with safe defaults
* Shapes ``possible_causes``, ``context_assessment``, recommendation buckets

The output of ``validate_rca_llm_output`` is what the API projects as
``RcaResponse`` (via ``logic.validate_output``).

Public API
----------
* ``validate_rca_llm_output`` — sole entry used by the graph validate node

Helpers below are private (``_``) normalization utilities.
"""

from __future__ import annotations

from typing import Any

from edim_dde_domain.agents.spark_rca.helpers.classify import RCA_CATEGORIES

# Map verbal confidence labels (if the model emits them) onto floats.
_CONFIDENCE_LABELS = {
    "high": 0.85,
    "medium": 0.6,
    "low": 0.3,
}

# Free-text category aliases → closed taxonomy. Keep soft; prefer hint on miss.
_CATEGORY_ALIASES = {
    "executor out-of-memory": "resource",
    "executor oom": "resource",
    "driver out-of-memory": "resource",
    "driver oom": "resource",
    "oom": "resource",
    "data skew": "skew_shuffle",
    "skew": "skew_shuffle",
    "cartesian join": "sql_error",
    "cartesian product": "sql_error",
    "delta storage lock": "config",
    "concurrent append": "config",
    "small file bottleneck": "config",
    "small files": "config",
    "schema mismatch": "data_quality",
    "delta schema": "data_quality",
}


def _clamp_confidence(value: Any, default: float = 0.4) -> float:
    """Parse and clamp a confidence value into ``[0.0, 1.0]``.

    Args:
        value: Numeric or numeric-string confidence from the LLM.
        default: Used when parsing fails.

    Returns:
        Float in inclusive range 0..1.
    """
    try:
        c = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, c))


def _confidence_from_raw(raw: dict[str, Any], default: float) -> float:
    """Prefer numeric ``confidence``, else map ``confidence_label``."""
    if raw.get("confidence") is not None:
        return _clamp_confidence(raw.get("confidence"), default=default)
    label = str(raw.get("confidence_label") or "").strip().lower()
    if label in _CONFIDENCE_LABELS:
        return _CONFIDENCE_LABELS[label]
    return default


def _normalize_category(raw: dict[str, Any], classification_hint: dict[str, Any]) -> str:
    """Map model category (or alias) onto ``RCA_CATEGORIES``.

    Falls back to the rule hint, then ``unknown``.
    """
    category = str(raw.get("category") or "").strip().lower()
    if category in RCA_CATEGORIES:
        return category
    alias = _CATEGORY_ALIASES.get(category)
    if alias:
        return alias
    for needle, mapped in _CATEGORY_ALIASES.items():
        if needle in category:
            return mapped
    return str(classification_hint.get("category") or "unknown")


def _as_str_list(value: Any) -> list[str]:
    """Coerce a scalar or list into a list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value).strip()
    return [text] if text else []


def _flatten_recommendations(raw: dict[str, Any]) -> list[str]:
    """Prefer flat ``recommended_actions``; else merge structured buckets."""
    actions = _as_str_list(raw.get("recommended_actions"))
    if actions:
        return actions[:10]
    rec = raw.get("recommendations")
    if not isinstance(rec, dict):
        return []
    merged: list[str] = []
    for key in ("code_query_rewrites", "spark_delta_configs", "infrastructure"):
        for item in _as_str_list(rec.get(key)):
            if item not in merged:
                merged.append(item)
    return merged[:10]


def _factors_from_raw(raw: dict[str, Any]) -> list[str]:
    """Build contributing factors from explicit list or evidence_analysis prose."""
    factors = _as_str_list(raw.get("contributing_factors"))
    if factors:
        return factors[:10]
    analysis = raw.get("evidence_analysis")
    if not isinstance(analysis, dict):
        return []
    out: list[str] = []
    for key, label in (
        ("log_signals", "Log signals"),
        ("metric_anomalies", "Metric anomalies"),
        ("physical_plan_bottlenecks", "Physical plan bottlenecks"),
    ):
        text = str(analysis.get(key) or "").strip()
        if text:
            out.append(f"{label}: {text}")
    return out[:10]


def _normalize_recommendations_block(raw: dict[str, Any]) -> dict[str, list[str]]:
    """Ensure the three structured recommendation buckets always exist."""
    rec = raw.get("recommendations")
    if not isinstance(rec, dict):
        rec = {}
    return {
        "code_query_rewrites": _as_str_list(rec.get("code_query_rewrites"))[:10],
        "spark_delta_configs": _as_str_list(rec.get("spark_delta_configs"))[:10],
        "infrastructure": _as_str_list(rec.get("infrastructure"))[:10],
    }


def _normalize_evidence_analysis(raw: dict[str, Any]) -> dict[str, str]:
    """Clamp evidence_analysis to the three prompt/schema channels."""
    analysis = raw.get("evidence_analysis")
    if not isinstance(analysis, dict):
        analysis = {}
    return {
        "log_signals": str(analysis.get("log_signals") or "").strip(),
        "metric_anomalies": str(analysis.get("metric_anomalies") or "").strip(),
        "physical_plan_bottlenecks": str(
            analysis.get("physical_plan_bottlenecks") or ""
        ).strip(),
    }


def _normalize_possible_causes(
    raw: dict[str, Any], allowed_refs: set[str]
) -> list[dict[str, Any]]:
    """Keep at most five alternative causes; drop rows without verification.

    Supporting evidence refs must appear in the live pack (hallucinated refs
    are stripped).
    """
    rows = raw.get("possible_causes")
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows[:5]:
        if not isinstance(row, dict):
            continue
        cause = str(row.get("cause") or "").strip()
        verification = str(row.get("verification") or "").strip()
        if not cause or not verification:
            continue
        likelihood = str(row.get("likelihood") or "low").strip().lower()
        if likelihood not in {"low", "medium", "high"}:
            likelihood = "low"
        out.append(
            {
                "cause": cause[:500],
                "likelihood": likelihood,
                "supporting_evidence_refs": [
                    str(ref)
                    for ref in (row.get("supporting_evidence_refs") or [])
                    if str(ref) in allowed_refs
                ],
                "verification": verification[:800],
            }
        )
    return out


def _normalize_context_assessment(
    raw: dict[str, Any], allowed_web_urls: set[str]
) -> dict[str, Any]:
    """Normalize how the model assessed runbooks / history / web.

    Web citations must be a subset of URLs returned by the web-search provider
    for this run (empty when search was disabled).
    """
    value = raw.get("context_assessment")
    if not isinstance(value, dict):
        value = {}
    return {
        "runbooks": str(value.get("runbooks") or "not used").strip()[:800],
        "history": str(value.get("history") or "not used").strip()[:800],
        "web": str(value.get("web") or "not used").strip()[:800],
        "web_citations": [
            str(url)
            for url in (value.get("web_citations") or [])
            if str(url) in allowed_web_urls
        ][:5],
    }


def validate_rca_llm_output(
    raw: dict[str, Any],
    *,
    evidence_pack: dict[str, Any],
    classification_hint: dict[str, Any],
    web_search_hits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Clamp/normalize LLM JSON; fall back to rule classification when needed.

    Args:
        raw: Parsed LLM object (or soft-fallback stub from ``parse_llm_json``).
        evidence_pack: Authoritative pack for this run (citation allowlist).
        classification_hint: Rule hint used for category/confidence defaults.
        web_search_hits: Normalized hits from ``web.search`` (URL allowlist).

    Returns:
        Dict with ``job_status``, ``root_cause``, ``evidence``, ``timeline``,
        ``possible_causes``, ``context_assessment``, ``recommendations``, etc.
        Ready to embed under API ``result``.

    Example:
        >>> out = validate_rca_llm_output(
        ...     {\"category\": \"oom\", \"summary\": \"Executor OOM\", \"recommended_actions\": [\"Increase memory\"]},
        ...     evidence_pack={\"evidence\": [{\"ref\": \"e1\", \"excerpt\": \"OOM\"}]},
        ...     classification_hint={\"category\": \"resource\", \"confidence\": 0.7},
        ... )
        >>> out[\"root_cause\"][\"category\"]
        'resource'
    """
    allowed_refs = {
        str(e.get("ref")) for e in (evidence_pack.get("evidence") or []) if e.get("ref")
    }
    category = _normalize_category(raw, classification_hint)
    allowed_web_urls = {
        str(hit.get("url"))
        for hit in (web_search_hits or [])
        if isinstance(hit, dict) and hit.get("url")
    }

    summary = str(raw.get("summary") or "").strip()
    if not summary:
        # Prefer live failure reason over a hollow "unknown" summary.
        pe = (evidence_pack.get("raw_anchors") or {}).get("pipeline_end") or {}
        summary = (
            pe.get("failure_reason")
            or classification_hint.get("rationale")
            or "Unable to determine a specific root cause from available evidence."
        )

    evidence_refs = [
        str(r) for r in (raw.get("evidence_refs") or []) if str(r) in allowed_refs
    ]
    # If the model forgot citations but pack has refs, surface a few for UX.
    if not evidence_refs and allowed_refs:
        evidence_refs = list(allowed_refs)[:3]

    evidence_out: list[dict[str, Any]] = []
    by_ref = {str(e.get("ref")): e for e in (evidence_pack.get("evidence") or [])}
    for ref in evidence_refs:
        item = by_ref.get(ref)
        if item:
            evidence_out.append(
                {
                    "source": item.get("source"),
                    "ref": ref,
                    "excerpt": item.get("excerpt"),
                }
            )

    timeline = raw.get("timeline_highlights")
    if not isinstance(timeline, list) or not timeline:
        timeline = evidence_pack.get("timeline") or []
    timeline_out: list[dict[str, Any]] = []
    for t in timeline[:12]:
        if not isinstance(t, dict):
            continue
        timeline_out.append(
            {
                "ts": t.get("ts"),
                "event_type": t.get("event_type"),
                "summary": str(t.get("summary") or "")[:240],
            }
        )

    contributing = _factors_from_raw(raw)
    actions = _flatten_recommendations(raw)
    if not actions:
        actions = ["Re-run with additional logging"]
    recommendations = _normalize_recommendations_block(raw)
    evidence_analysis = _normalize_evidence_analysis(raw)

    confidence = _confidence_from_raw(
        raw,
        default=float(classification_hint.get("confidence") or 0.4),
    )
    label = str(raw.get("confidence_label") or "").strip()
    if not label:
        if confidence >= 0.75:
            label = "High"
        elif confidence >= 0.45:
            label = "Medium"
        else:
            label = "Low"

    job_status = str(raw.get("job_status") or "FAILED").strip().upper().replace(" ", "_")
    if job_status not in {"FAILED", "DEGRADED", "SUCCESS_WITH_WARNINGS"}:
        job_status = "FAILED"

    signature = str(raw.get("failure_signature") or "").strip() or category

    return {
        "job_status": job_status,
        "root_cause": {
            "category": category,
            "summary": str(summary),
            "confidence": confidence,
            "model_confidence": confidence,
            "confidence_label": label,
            "failure_signature": signature[:256],
        },
        "evidence_analysis": evidence_analysis,
        "possible_causes": _normalize_possible_causes(raw, allowed_refs),
        "context_assessment": _normalize_context_assessment(raw, allowed_web_urls),
        "recommendations": recommendations,
        "timeline": timeline_out,
        "evidence": evidence_out,
        "contributing_factors": contributing,
        "recommended_actions": actions[:10],
        "raw_anchors": evidence_pack.get("raw_anchors") or {},
    }
