"""Spark-RCA ExperienceTransform using evidence features, not named scenarios."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from edim_dde_ai.experiences.models import ExperienceDocument
from edim_dde_ai.recommendations.models import RecommendationRecord

AGENT_ID = "spark_rca"
CORPUS = "spark-rca-outcomes"
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{2,80}")
_STOP = {
    "error",
    "exception",
    "failed",
    "failure",
    "spark",
    "java",
    "org",
    "com",
    "the",
    "and",
    "with",
    "from",
}


def _result(record: RecommendationRecord) -> dict[str, Any]:
    response = record.response if isinstance(record.response, dict) else {}
    result = response.get("result")
    return result if isinstance(result, dict) else response


def _pack(record: RecommendationRecord) -> dict[str, Any]:
    result = _result(record)
    pack = result.get("evidence_pack")
    if isinstance(pack, dict):
        return pack
    request = record.request if isinstance(record.request, dict) else {}
    pack = request.get("evidence_pack")
    return pack if isinstance(pack, dict) else {}


def _signature_tokens(value: Any, *, limit: int = 8) -> list[str]:
    """Extract bounded, open-vocabulary technical tokens for similarity search."""
    out: list[str] = []
    for match in _TOKEN_RE.findall(str(value or "")):
        token = match.strip("._-").lower()
        if token in _STOP or token.isdigit() or len(token) < 3:
            continue
        if token not in out:
            out.append(token)
        if len(out) >= limit:
            break
    return out


def infer_failure_features(
    *,
    evidence_pack: dict[str, Any],
    classification_hint: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
) -> list[str]:
    """Derive open evidence features; taxonomy is descriptive, not authoritative."""
    hint = classification_hint or {}
    output = result or {}
    root = output.get("root_cause") or {}
    features: list[str] = []

    for prefix, category in (
        ("hint", hint.get("category")),
        ("root", root.get("category")),
    ):
        value = str(category or "").strip().lower()
        if value:
            features.append(f"{prefix}_category_{value}")

    evidence = [
        item
        for item in (evidence_pack.get("evidence") or [])
        if isinstance(item, dict)
    ]
    for source in sorted(
        {str(item.get("source") or "").strip().lower() for item in evidence}
    ):
        if source:
            features.append(f"evidence_source_{source}")

    sections = evidence_pack.get("sections") or {}
    for name in ("logs", "stage_metrics", "sql_plans"):
        section = sections.get(name)
        if isinstance(section, dict) and any(section.values()):
            features.append(f"evidence_channel_{name}")

    anchors = evidence_pack.get("raw_anchors") or {}
    signature_text = " ".join(
        [
            str(root.get("failure_signature") or ""),
            str(anchors.get("failure_reason") or ""),
            str((anchors.get("pipeline_end") or {}).get("failure_reason") or ""),
            " ".join(str(item.get("excerpt") or "") for item in evidence[:4]),
        ]
    )
    features.extend(f"signal_{token}" for token in _signature_tokens(signature_text))
    if not features:
        features.append("failure_signal_unknown")
    return list(dict.fromkeys(features))


def build_experience_query(state: dict[str, Any]) -> str:
    pack = state.get("evidence_pack")
    if not isinstance(pack, dict):
        pack = {}
    hint = state.get("classification_hint")
    if not isinstance(hint, dict):
        hint = {}
    features = infer_failure_features(
        evidence_pack=pack,
        classification_hint=hint,
    )
    return " ".join(
        [
            "databricks spark job failure past diagnosis outcome",
            *features,
            "root cause contributing factors fixes actions",
        ]
    )


def _actions(result: dict[str, Any]) -> list[str]:
    rows = result.get("recommended_actions") or []
    if not isinstance(rows, list):
        return []
    return [str(value).strip() for value in rows if str(value).strip()][:8]


def _action_signature(result: dict[str, Any]) -> str:
    root = result.get("root_cause") or {}
    normalized = "|".join(
        [
            str(root.get("category") or "unknown").lower(),
            *[
                re.sub(r"\s+", " ", action.lower()).strip()
                for action in _actions(result)
            ],
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]


class SparkRcaExperienceTransform:
    @property
    def agent_id(self) -> str:
        return AGENT_ID

    @property
    def corpus(self) -> str:
        return CORPUS

    def transform(self, record: RecommendationRecord) -> ExperienceDocument | None:
        # RCA diagnoses should become cross-job precedent only after review or
        # application. Proposed rows remain available in exact entity history.
        if str(record.status or "").lower() not in {"accepted", "applied"}:
            return None
        result = _result(record)
        pack = _pack(record)
        hint = result.get("classification_hint")
        if not isinstance(hint, dict):
            hint = {}
        root = result.get("root_cause")
        if not isinstance(root, dict):
            root = {}
        features = infer_failure_features(
            evidence_pack=pack,
            classification_hint=hint,
            result=result,
        )
        actions = _actions(result)
        analysis = result.get("evidence_analysis") or {}
        text = "\n".join(
            [
                f"Failure features: {', '.join(features)}",
                "Diagnosis: "
                + str(root.get("summary") or root.get("failure_signature") or "unknown"),
                "Evidence analysis: "
                + "; ".join(
                    str(value).strip()
                    for value in analysis.values()
                    if str(value).strip()
                ),
                "Actions: " + ("; ".join(actions) if actions else "none recorded"),
                f"Outcome: {record.status}",
            ]
        )
        signature = _action_signature(result)
        return ExperienceDocument(
            doc_id=record.recommendation_id,
            corpus=CORPUS,
            text=text,
            feature_labels=features,
            action_signature=signature,
            metadata={
                "agent_id": AGENT_ID,
                "job_id": record.job_id,
                "job_run_id": record.job_run_id,
                "recommendation_id": record.recommendation_id,
                "status": record.status,
                "feature_labels": features,
                "action_signature": signature,
                "root_category": root.get("category"),
                "failure_signature": root.get("failure_signature"),
            },
            source=f"recommendation:{record.recommendation_id}",
        )


def register_spark_rca_experience_transform() -> None:
    from edim_dde_ai.experiences import register_experience_transform

    register_experience_transform(SparkRcaExperienceTransform())
