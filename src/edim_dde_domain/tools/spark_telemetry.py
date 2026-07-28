"""Legacy stub helper for tests — prefer agent graph + domain.sql.query."""

from __future__ import annotations

from typing import Any, Optional


def build_evidence_pack_for_run(
    *,
    job_run_id: str,
    job_id: Optional[str] = None,
    error_text: Optional[str] = None,
    evidence_pack_override: Optional[dict[str, Any]] = None,
    **_ignored: Any,
) -> dict[str, Any]:
    """Build a minimal evidence pack (override or stub). No SQL."""
    if isinstance(evidence_pack_override, dict) and evidence_pack_override:
        return evidence_pack_override
    reason = str(error_text or "Unknown failure")
    return {
        "job_run_id": job_run_id,
        "job_id": job_id,
        "evidence": [
            {
                "ref": "e1",
                "source": "spark_logs",
                "excerpt": reason[:400],
            }
        ],
        "raw_anchors": {"failure_reason": reason},
        "sections": {},
        "timeline": [],
    }
