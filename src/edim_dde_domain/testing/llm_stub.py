"""Deterministic LLM stand-in for offline tests (not used in production)."""

from __future__ import annotations

import json
import re
from typing import Any


def _human_text(messages: list[tuple[str, str]]) -> str:
    for role, content in reversed(messages):
        if role == "human":
            return content
    return "\n".join(content for _, content in messages)


def _sizing_from_text(text: str) -> str:
    cpu_m = re.search(r"peak_worker_cpu_utilization_pct[\"']?\s*[:=]\s*([0-9.]+)", text)
    mem_m = re.search(r"peak_worker_memory_utilization_pct[\"']?\s*[:=]\s*([0-9.]+)", text)
    max_m = re.search(r"max_worker_nodes_provisioned[\"']?\s*[:=]\s*([0-9]+)", text)
    type_m = re.search(r"azure_worker_vm_size[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9_]+)", text)
    hints_max = re.search(r"recommended_max_workers[\"']?\s*[:=]\s*([0-9]+)", text)

    peak_cpu = float(cpu_m.group(1)) if cpu_m else 50.0
    peak_mem = float(mem_m.group(1)) if mem_m else 50.0
    current_max = int(max_m.group(1)) if max_m else 16
    current_type = type_m.group(1) if type_m else "Standard_E8s_v3"
    util = max(peak_cpu, peak_mem)
    floor_max = int(hints_max.group(1)) if hints_max else max(2, current_max // 2)

    # On guardrail retry feedback, prefer policy-compliant workers / auto_term.
    retrying = bool(
        re.search(
            r"Previous recommendation violated policy|required_applied=",
            text,
            re.I,
        )
    )

    if util < 40:
        rec_max = max(floor_max, max(2, current_max // 2))
        family = (
            "E" if "Standard_E" in current_type
            else "F" if "Standard_F" in current_type
            else "L" if "Standard_L" in current_type
            else "D"
        )
        size_m = re.search(r"Standard_[DEFL](\d+)", current_type, re.I)
        current_vcpus = int(size_m.group(1)) if size_m else 4
        vcpus = max(4, current_vcpus // 2)
        pattern = (
            "### 1. Workload type\nLow utilization batch job.\n\n"
            "### 2. Resource utilization\n"
            f"Peak util {util:.0f}%.\n\n"
            "### 3. Performance characteristics\nHeadroom available.\n\n"
            "### 4. Optimization opportunities\nDownsize vCPU tier and max workers; keep family."
        )
    elif util > 80:
        rec_max = max(floor_max, min(current_max + 4, 32))
        family = "E" if "E" in current_type else "D"
        vcpus = 8 if "8" in current_type or "16" in current_type else 4
        pattern = (
            "### 1. Workload type\nHigh utilization job.\n\n"
            "### 2. Resource utilization\n"
            f"Peak util {util:.0f}%.\n\n"
            "### 3. Performance characteristics\nNear capacity.\n\n"
            "### 4. Optimization opportunities\nRaise max workers; keep family."
        )
    else:
        rec_max = max(floor_max, current_max)
        family = "E" if "E" in current_type else "D"
        vcpus = 8 if "8" in current_type else 4
        pattern = (
            "### 1. Workload type\nSteady utilization.\n\n"
            "### 2. Resource utilization\n"
            f"Peak util {util:.0f}%.\n\n"
            "### 3. Performance characteristics\nIn band.\n\n"
            "### 4. Optimization opportunities\nKeep current sizing."
        )

    if retrying:
        rec_max = max(rec_max, floor_max)

    history_present = "### Similar past experiences" in text or "### Retrieved sizing guidance" in text
    history_note = (
        "Relevant historical experience/guidance corroborates the direction; live metrics remain primary."
        if history_present
        else "No relevant historical evidence was available; decision uses live metrics and sizing hints."
    )
    pattern += f"\n\n### 5. Historical evidence\n{history_note}"

    return json.dumps(
        {
            "pattern_analysis": pattern,
            "node_family": family,
            "vcpus": vcpus,
            "min_workers": 0,
            "max_workers": rec_max,
            "auto_termination_minutes": 0,
            "rationale": (
                f"Peak util {util:.0f}%; current max={current_max}, type={current_type}."
            ),
        }
    )


def _rca_from_text(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ("oom", "out of memory", "heap space")):
        category, confidence = "resource", 0.85
        summary = "Likely executor/driver OOM based on evidence."
        actions = [
            "Inspect executor memory and spill metrics",
            "Re-run with additional logging",
        ]
    elif (
        "table not found" in lower
        or "analysisexception" in lower
        or "sql_error" in lower
    ):
        category, confidence = "sql_error", 0.8
        summary = "Likely SQL/analysis error based on evidence."
        actions = ["Verify table names and schema", "Re-run with additional logging"]
    elif any(k in lower for k in ("timeout", "cancelled")):
        category, confidence = "timeout_or_cancel", 0.7
        summary = "Likely timeout or cancel based on evidence."
        actions = [
            "Check job timeouts and cancel signals",
            "Re-run with additional logging",
        ]
    else:
        category, confidence = "unknown", 0.4
        summary = "Insufficient evidence for a precise root cause."
        actions = ["Inspect full failure_reason/stack", "Re-run with additional logging"]

    refs = re.findall(r'"ref"\s*:\s*"([^"]+)"', text)
    return json.dumps(
        {
            "job_status": "FAILED",
            "category": category,
            "confidence": confidence,
            "confidence_label": (
                "High" if confidence >= 0.75 else "Medium" if confidence >= 0.45 else "Low"
            ),
            "summary": summary,
            "failure_signature": category,
            "evidence_analysis": {
                "log_signals": summary,
                "metric_anomalies": "",
                "physical_plan_bottlenecks": "",
            },
            "contributing_factors": [summary],
            "recommended_actions": actions,
            "recommendations": {
                "code_query_rewrites": [],
                "spark_delta_configs": [],
                "infrastructure": [],
            },
            "evidence_refs": refs[:8],
            "timeline_highlights": [],
        }
    )


def _explanation_from_text(text: str) -> str:
    return (
        "### 1. Rationale\n"
        "Recommendation follows observed utilization in this job run.\n\n"
        "### 2. Evidence\n"
        "See job run ingest and pattern analysis in the prompt.\n\n"
        "### 3. Current vs recommended configuration\n"
        f"{text[:400]}\n\n"
        "### 4. Expected impact\n"
        "Better fit between provisioned capacity and observed demand.\n\n"
        "### 5. Risks and mitigations\n"
        "Validate on a non-prod run before applying broadly.\n\n"
        "### 6. Alternatives\n"
        "Keep current sizing if upcoming workload peaks are expected."
    )


class DomainStubLLM:
    """Fake LLMProvider for offline tests (import from edim_dde_domain.testing)."""

    def invoke(
        self,
        messages: list[tuple[str, str]],
        *,
        config: dict[str, Any] | None = None,
    ) -> str:
        chain = str((config or {}).get("chain") or "")
        text = _human_text(messages)
        if chain == "sizing":
            return _sizing_from_text(text)
        if chain == "rca":
            return _rca_from_text(text)
        if chain == "explanation":
            return _explanation_from_text(text)
        return json.dumps({"summary": "stub", "category": "unknown", "confidence": 0.4})
