"""Spark RCA → experience-index transform (cross-job learning lane).

Business purpose
----------------
When an engineer **accepts** or **applies** an RCA recommendation, this module
turns that lifecycle record into an ``ExperienceDocument`` and (via the platform
``ExperienceIndexingStore`` wrapper) upserts it into the ``spark-rca-outcomes``
retrieval corpus.

Later RCA runs retrieve **feature-similar** past outcomes — not by ``job_id`` —
so the LLM can see how similar failures were diagnosed and fixed. Proposed rows
are **not** indexed into the cross-job corpus; they remain available only through
exact entity history (RecommendationStore list by job/run).

Design principles
-----------------
* Features are **open / structural** (channels, exception-class tokens, sources),
  not a closed scenario enum (``oom``, ``small_files``, skill filenames, …).
* ``job_id`` / ``job_run_id`` go in **metadata** for display, never as the
  primary similarity key in index text or search queries.
* Empty / non-accepted records → transform returns ``None`` (no index write).

Public API
----------
* ``infer_failure_features`` — shared feature vocabulary for index + query
* ``build_experience_query`` — live-state query for ``search_corpus``
* ``SparkRcaExperienceTransform`` — ``ExperienceTransform`` protocol impl
* ``register_spark_rca_experience_transform`` — bootstrap hook

See also: ``historical_context.py``, platform ``edim_dde_ai.experiences``.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from edim_dde_ai.experiences.models import ExperienceDocument
from edim_dde_ai.recommendations.models import RecommendationRecord

AGENT_ID = "spark_rca"
CORPUS = "spark-rca-outcomes"

# Open-vocabulary token extractor for failure signatures / excerpts.
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
    """Unwrap ``response`` or nested ``response.result`` into the RCA payload.

    Args:
        record: Persisted recommendation lifecycle row.

    Returns:
        Dict shaped like ``RcaResponse`` fields (root_cause, evidence_pack, …).
    """
    response = record.response if isinstance(record.response, dict) else {}
    result = response.get("result")
    return result if isinstance(result, dict) else response


def _pack(record: RecommendationRecord) -> dict[str, Any]:
    """Locate evidence_pack on the stored response, then fall back to request.

    Persist paths often omit the request pack (size) but keep a bounded snapshot
    on the response for feature fidelity.

    Args:
        record: Persisted recommendation lifecycle row.

    Returns:
        Evidence pack dict, or ``{}`` if neither side has one.
    """
    result = _result(record)
    pack = result.get("evidence_pack")
    if isinstance(pack, dict):
        return pack
    request = record.request if isinstance(record.request, dict) else {}
    pack = request.get("evidence_pack")
    return pack if isinstance(pack, dict) else {}


def _signature_tokens(value: Any, *, limit: int = 8) -> list[str]:
    """Extract bounded, open-vocabulary technical tokens for similarity search.

    Stops on common English/Java package noise and numeric-only tokens so the
    feature space stays retrieval-friendly without a fixed taxonomy.

    Args:
        value: Free text (failure reason, excerpts, signature, …).
        limit: Max distinct tokens to keep (order-preserving).

    Returns:
        Lowercased unique tokens, length-capped.

    Example:
        >>> _signature_tokens("Executor OutOfMemoryError: Java heap space")
        ['outofmemoryerror', 'heap', 'space']
    """
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
    """Derive open evidence features for indexing and live experience queries.

    Taxonomy categories (``hint_category_*`` / ``root_category_*``) are
    **descriptive labels only** — they must not be the sole retrieval vocabulary.
    Structural channels and ``signal_*`` tokens carry similarity across unseen
    failures.

    Args:
        evidence_pack: Current or stored evidence pack (sections, anchors, evidence).
        classification_hint: Optional rule-classifier output from the live run.
        result: Optional stored/validated RCA result (adds root-cause category).

    Returns:
        Deduped feature label strings, e.g.
        ``['hint_category_resource', 'evidence_channel_logs', 'signal_outofmemoryerror']``.
        Always at least ``failure_signal_unknown`` when nothing else is present.

    Example:
        >>> infer_failure_features(
        ...     evidence_pack={
        ...         "sections": {"logs": {"a": 1}},
        ...         "evidence": [{"source": "logs", "excerpt": "OutOfMemoryError"}],
        ...     },
        ...     classification_hint={"category": "resource"},
        ... )
        ['hint_category_resource', 'evidence_source_logs', ...]
    """
    hint = classification_hint or {}
    output = result or {}
    root = output.get("root_cause") or {}
    features: list[str] = []

    # Soft taxonomy labels (metadata-like); retrieval also uses signal_* below.
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

    # Presence of major evidence channels (not the channel contents).
    sections = evidence_pack.get("sections") or {}
    for name in ("logs", "stage_metrics", "sql_plans"):
        section = sections.get(name)
        if isinstance(section, dict) and any(section.values()):
            features.append(f"evidence_channel_{name}")

    # Open tokens from signature + failure reason + short excerpts.
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
    """Build a feature-based retrieval query from the **live** agent state.

    Intentionally omits ``job_id`` / ``job_run_id`` so search is similarity-based
    across jobs. Used by ``compose_historical_context`` → ``search_corpus``.

    Args:
        state: Graph state with ``evidence_pack`` and optional ``classification_hint``.

    Returns:
        Free-text query string for the ``spark-rca-outcomes`` corpus.

    Example:
        >>> q = build_experience_query({
        ...     "evidence_pack": {"evidence": [{"excerpt": "AnalysisException"}]},
        ...     "classification_hint": {"category": "sql_error"},
        ... })
        >>> "hint_category_sql_error" in q and "job_id" not in q
        True
    """
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
    """Bounded flat action lines from a validated RCA result."""
    rows = result.get("recommended_actions") or []
    if not isinstance(rows, list):
        return []
    return [str(value).strip() for value in rows if str(value).strip()][:8]


def _action_signature(result: dict[str, Any]) -> str:
    """Stable short hash for dedupe of semantically identical action sets.

    Combines root category + normalized action text. Platform
    ``dedupe_retrieval_hits`` collapses duplicate signatures across jobs and
    surfaces ``occurrences`` / ``also_job_ids``.

    Args:
        result: Validated RCA payload.

    Returns:
        20-char hex digest (not meant for human display).
    """
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
    """Map accepted/applied ``RecommendationRecord`` → ``ExperienceDocument``.

    Registered once at domain bootstrap. The RecommendationStore wrapper calls
    ``transform`` on save / status update; rejected/superseded docs are deleted
    by the platform indexer (this class returns ``None`` for non-accepted statuses
    so proposed rows never enter the cross-job corpus).

    Attributes:
        agent_id: Always ``spark_rca`` (store filter / registration key).
        corpus: Always ``spark-rca-outcomes``.
    """

    @property
    def agent_id(self) -> str:
        """Agent id this transform is bound to."""
        return AGENT_ID

    @property
    def corpus(self) -> str:
        """Retrieval corpus name for upserts."""
        return CORPUS

    def transform(self, record: RecommendationRecord) -> ExperienceDocument | None:
        """Build an experience card, or ``None`` to skip indexing.

        Args:
            record: Lifecycle row after ``store.save`` / ``update_status``.

        Returns:
            ``ExperienceDocument`` when status is ``accepted`` or ``applied``
            and enough payload exists; otherwise ``None``.

        Example:
            Only ``accepted`` / ``applied`` produce documents::

                transform(proposed_record)  -> None
                transform(accepted_record)  -> ExperienceDocument(...)
        """
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
        # Card text is what embedding / hybrid search reads; keep it structural.
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
    """Register this transform with the process-wide experience registry.

    Called from ``edim_dde_domain.bootstrap`` during agent bootstrap. Safe to
    call once per process; re-registration replaces the prior transform for
    ``spark_rca``.
    """
    from edim_dde_ai.experiences import register_experience_transform

    register_experience_transform(SparkRcaExperienceTransform())
