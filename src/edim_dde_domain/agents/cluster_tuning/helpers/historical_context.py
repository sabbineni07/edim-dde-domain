"""Build historical_context for cluster_tuning sizing prompts.

Two complementary sources (product parity):

1. **RecommendationStore** — past proposals ranked by job_id match first, then
   metric/SKU similarity (top-N from YAML node config)
2. **RetrievalProvider** — optional ``rag.retrieve`` hits (guidance corpus)

Either source may be empty; sizing still runs with ``historical_context: "None"``.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_EMPTY = "None"
_DEFAULT_JOB_TOP_N = 5
_DEFAULT_SIMILAR_TOP_N = 5
_DEFAULT_CANDIDATE_LIMIT = 80
_MAX_CHARS = 6000
_STATUS_RANK = {"applied": 0, "accepted": 1, "proposed": 2, "superseded": 3, "rejected": 4}


def default_history_config() -> dict[str, Any]:
    """Defaults when YAML omits history knobs on ``prepare_sizing_payload``."""
    return {
        "history_job_top_n": _DEFAULT_JOB_TOP_N,
        "history_similar_top_n": _DEFAULT_SIMILAR_TOP_N,
        "history_candidate_limit": _DEFAULT_CANDIDATE_LIMIT,
        "history_prefer_statuses": ["applied", "accepted", "proposed"],
    }


def merge_history_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    cfg = default_history_config()
    if not raw:
        return cfg
    for key in (
        "history_job_top_n",
        "history_similar_top_n",
        "history_candidate_limit",
    ):
        if key in raw and raw[key] is not None:
            cfg[key] = max(0, int(raw[key]))
    if raw.get("history_prefer_statuses"):
        cfg["history_prefer_statuses"] = [
            str(s).strip().lower() for s in raw["history_prefer_statuses"] if str(s).strip()
        ]
    return cfg


def build_retrieval_query(state: dict[str, Any]) -> dict[str, Any]:
    """Free-text query for cluster-tuning guidance similarity search."""
    metrics = state.get("metrics") or {}
    if not isinstance(metrics, dict):
        metrics = {}
    sku = str(metrics.get("azure_worker_vm_size") or "").strip()
    max_w = metrics.get("max_worker_nodes_provisioned")
    peak_cpu = metrics.get("peak_worker_cpu_utilization_pct")
    peak_mem = metrics.get("peak_worker_memory_utilization_pct")
    avg_nodes = metrics.get("avg_worker_nodes_consumed")
    parts = [
        "databricks cluster rightsizing worker sku underutilization",
        f"sku={sku}" if sku else "",
        f"max_workers={max_w}" if max_w is not None else "",
        f"peak_cpu_pct={peak_cpu}" if peak_cpu is not None else "",
        f"peak_memory_pct={peak_mem}" if peak_mem is not None else "",
        f"avg_worker_nodes={avg_nodes}" if avg_nodes is not None else "",
    ]
    query = " ".join(p for p in parts if p).strip() or "cluster sizing rightsizing"
    return {"retrieval_query": query}


def _rec_attr(rec: Any, key: str, default: Any = None) -> Any:
    if hasattr(rec, key) and not key.startswith("_"):
        # Annotated dicts use keys; dataclass attrs for real records.
        val = getattr(rec, key, default)
        if val is not None or key in getattr(rec, "__dataclass_fields__", {}):
            return val
    if isinstance(rec, dict):
        return rec.get(key, default)
    return getattr(rec, key, default)


def _rec_response(rec: Any) -> dict[str, Any]:
    response = _rec_attr(rec, "response") or {}
    return response if isinstance(response, dict) else {}


def _rec_request(rec: Any) -> dict[str, Any]:
    request = _rec_attr(rec, "request") or {}
    return request if isinstance(request, dict) else {}


def _metrics_from_record(rec: Any) -> dict[str, Any]:
    """Best-effort metrics snapshot from stored request/response payloads."""
    response = _rec_response(rec)
    request = _rec_request(rec)
    for blob in (
        response.get("job_cluster_metrics"),
        request.get("metrics"),
        response.get("current_configuration"),
    ):
        if isinstance(blob, dict) and blob:
            return blob
    return {}


def format_store_history(
    records: list[Any],
    *,
    max_rows: int | None = None,
    title: str = "### Prior recommendations",
) -> str:
    """Render RecommendationRecord-like rows for the sizing prompt."""
    if not records:
        return ""
    limit = len(records) if max_rows is None else max_rows
    lines: list[str] = [title]
    for i, rec in enumerate(records[:limit], start=1):
        status = _rec_attr(rec, "status")
        created = _rec_attr(rec, "created_at")
        job_id = _rec_attr(rec, "job_id")
        cluster_id = _rec_attr(rec, "cluster_id")
        score = _rec_attr(rec, "_similarity_score")
        match_kind = _rec_attr(rec, "_match_kind")
        response = _rec_response(rec)
        recommendation = response.get("recommendation") or {}
        reason_codes = response.get("reason_codes") or recommendation.get("reason_codes") or []
        summary: dict[str, Any] = {
            "job_id": job_id,
            "cluster_id": cluster_id,
            "status": status,
            "created_at": created,
            "recommended_node_type": recommendation.get("recommended_node_type")
            or recommendation.get("azure_worker_vm_size"),
            "max_workers": recommendation.get("recommended_max_workers")
            or recommendation.get("max_workers"),
            "min_workers": recommendation.get("min_workers"),
            "reason_codes": list(reason_codes)[:8] if reason_codes else [],
            "risk_level": (response.get("risk_assessment") or {}).get("level")
            or recommendation.get("risk_level"),
        }
        if match_kind:
            summary["match"] = match_kind
        if score is not None:
            summary["similarity"] = round(float(score), 3)
        lines.append(f"[{i}] {summary}")
    return "\n".join(lines)


def _as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _token_set(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) > 2}


def similarity_score(state: dict[str, Any], rec: Any) -> float:
    """Heuristic similarity: SKU match + numeric closeness + token overlap.

    Not embeddings — ranks RecommendationStore rows without requiring RAG.
    """
    metrics = state.get("metrics") or {}
    if not isinstance(metrics, dict):
        metrics = {}
    other = _metrics_from_record(rec)
    score = 0.0

    sku_a = str(metrics.get("azure_worker_vm_size") or "").strip().lower()
    sku_b = str(other.get("azure_worker_vm_size") or "").strip().lower()
    if sku_a and sku_b and sku_a == sku_b:
        score += 3.0
    elif sku_a and sku_b:
        parts_a = sku_a.replace("standard_", "").split("_")
        parts_b = sku_b.replace("standard_", "").split("_")
        if parts_a and parts_b and parts_a[0] == parts_b[0]:
            score += 1.0

    for key, weight, scale in (
        ("max_worker_nodes_provisioned", 1.5, 16.0),
        ("peak_worker_cpu_utilization_pct", 1.0, 50.0),
        ("peak_worker_memory_utilization_pct", 1.0, 50.0),
        ("avg_worker_nodes_consumed", 1.0, 8.0),
        ("p99_worker_nodes_consumed", 1.0, 8.0),
    ):
        a = _as_float(metrics.get(key))
        b = _as_float(other.get(key))
        if a is None or b is None:
            continue
        dist = abs(a - b) / max(scale, 1.0)
        score += weight * max(0.0, 1.0 - min(dist, 1.0))

    response = _rec_response(rec)
    recommendation = response.get("recommendation") or {}
    hay = " ".join(
        [
            str(recommendation.get("recommended_node_type") or ""),
            " ".join(str(c) for c in (response.get("reason_codes") or [])),
            str(sku_b),
        ]
    )
    query = " ".join(
        str(metrics.get(k) or "")
        for k in (
            "azure_worker_vm_size",
            "max_worker_nodes_provisioned",
            "peak_worker_cpu_utilization_pct",
            "peak_worker_memory_utilization_pct",
        )
    )
    ta, tb = _token_set(query), _token_set(hay)
    if ta and tb:
        score += 0.5 * (len(ta & tb) / len(ta | tb))

    status = str(_rec_attr(rec, "status") or "").lower()
    score += max(0.0, 0.4 - 0.1 * _STATUS_RANK.get(status, 5))
    return score


def _annotate(rec: Any, *, match_kind: str, score: float | None = None) -> dict[str, Any]:
    data = rec.to_dict() if hasattr(rec, "to_dict") else dict(rec)
    data["_match_kind"] = match_kind
    if score is not None:
        data["_similarity_score"] = float(score)
    return data


def _rec_id(rec: Any) -> str:
    rid = _rec_attr(rec, "recommendation_id")
    return str(rid) if rid else str(id(rec))


def select_history_records(
    state: dict[str, Any],
    records: list[Any],
    *,
    config: dict[str, Any] | None = None,
) -> list[Any]:
    """Prefer same job_id; always fill with similar other-job rows up to similar_top_n.

    - ``history_job_top_n``: max rows with matching job_id (status preference applied)
    - ``history_similar_top_n``: max additional similar rows (other jobs, or when
      job_id has no history). Runs even when job matches exist, so similar peer
      jobs can still inform sizing.
    """
    cfg = merge_history_config(config)
    job_top_n = int(cfg["history_job_top_n"])
    similar_top_n = int(cfg["history_similar_top_n"])
    prefer = list(cfg["history_prefer_statuses"])

    job_id = str(state.get("job_id") or "").strip()
    same_job = [r for r in records if job_id and str(_rec_attr(r, "job_id") or "") == job_id]

    def _status_pref(rec: Any) -> int:
        st = str(_rec_attr(rec, "status") or "").lower()
        try:
            return prefer.index(st)
        except ValueError:
            return len(prefer) + _STATUS_RANK.get(st, 9)

    # Newest first, then stable-sort by preferred status (keeps newest within each band)
    same_job_sorted = sorted(
        same_job,
        key=lambda r: str(_rec_attr(r, "created_at") or ""),
        reverse=True,
    )
    same_job_sorted = sorted(same_job_sorted, key=_status_pref)

    selected: list[Any] = [
        _annotate(r, match_kind="job_id") for r in same_job_sorted[:job_top_n]
    ]
    selected_ids = {_rec_id(r) for r in selected}

    if similar_top_n <= 0:
        return selected

    others = [r for r in records if _rec_id(r) not in selected_ids]
    scored = [(similarity_score(state, r), r) for r in others]
    scored.sort(key=lambda t: t[0], reverse=True)

    added = 0
    for score, rec in scored:
        if added >= similar_top_n:
            break
        # When we already have job matches, skip zero/near-zero noise
        if selected and score < 0.25:
            continue
        selected.append(_annotate(rec, match_kind="similar", score=score))
        added += 1
    return selected


def _load_store_history(
    state: dict[str, Any], *, config: dict[str, Any] | None = None
) -> str:
    """Best-effort list from RecommendationStore (never raises into the graph)."""
    try:
        from edim_dde_ai.recommendations import get_recommendation_store
    except Exception:  # noqa: BLE001
        return ""

    store = get_recommendation_store()
    if getattr(store, "name", "") == "none":
        return ""

    cfg = merge_history_config(config)
    candidate_limit = int(cfg["history_candidate_limit"])
    try:
        candidates = store.list(
            agent_id="cluster_tuning",
            limit=max(1, candidate_limit),
        )
        selected = select_history_records(state, candidates, config=cfg)
        if not selected:
            return ""
        job_n = sum(1 for r in selected if _rec_attr(r, "_match_kind") == "job_id")
        sim_n = len(selected) - job_n
        title = (
            "### Prior recommendations "
            f"(job_id matches={job_n}, similar={sim_n}; "
            f"job_top_n={cfg['history_job_top_n']}, "
            f"similar_top_n={cfg['history_similar_top_n']})"
        )
        return format_store_history(selected, title=title)
    except Exception as exc:  # noqa: BLE001
        logger.warning("historical_context store lookup failed: %s", exc)
        return ""


def compose_historical_context(
    state: dict[str, Any], *, config: dict[str, Any] | None = None
) -> str:
    """Merge store history + optional RAG guidance into one prompt string."""
    parts: list[str] = []

    store_block = _load_store_history(state, config=config)
    if store_block:
        parts.append(store_block)

    guidance = (
        state.get("guidance_context")
        or state.get("retrieval_context")
        or state.get("historical_guidance")
    )
    if guidance and str(guidance).strip() and str(guidance).strip() not in {
        _EMPTY,
        "(no runbook / knowledge hits retrieved)",
        "(no guidance hits retrieved)",
        "(no retrieval query)",
    }:
        parts.append("### Retrieved sizing guidance\n" + str(guidance).strip())

    if not parts:
        return _EMPTY

    text = "\n\n".join(parts)
    if len(text) > _MAX_CHARS:
        return text[: _MAX_CHARS - 20] + "\n…[truncated]"
    return text
