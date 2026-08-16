"""Subset of Databricks-efficiency allow-list for SKU validation.

Business purpose
----------------
The sizing LLM proposes ``node_family`` + ``vcpus`` (not a free-form Azure SKU).
Guardrails map that intent onto a concrete ``azure_node_type`` from this curated
allow-list so recommendations stay within approved worker shapes.

Used exclusively by ``guardrails.validate_and_clamp_with_adjustments`` after
family/vCPU clamps.

Public API
----------
* ``ALLOWED_AZURE_NODE_TYPES`` — set of permitted SKU strings
* ``compose_node_type`` — synthesize a Standard_* name when no allow-list hit
* ``nearest_allowed_node_type`` — map family/vCPU (+ optional current) to SKU
"""

from __future__ import annotations

from typing import Optional

ALLOWED_AZURE_NODE_TYPES: set[str] = {
    "Standard_D2ds_v6",
    "Standard_D2ads_v6",
    "Standard_D4ds_v5",
    "Standard_D4ads_v6",
    "Standard_D4ads_v5",
    "Standard_D4s_v5",
    "Standard_D4ds_v6",
    "Standard_D8ads_v6",
    "Standard_D8ds_v5",
    "Standard_D8ds_v6",
    "Standard_D8ads_v5",
    "Standard_D16ads_v6",
    "Standard_D16ds_v6",
    "Standard_D16ds_v5",
    "Standard_E2ads_v6",
    "Standard_E2ds_v6",
    "Standard_E4ds_v5",
    "Standard_E4s_v5",
    "Standard_E4ads_v5",
    "Standard_E4ads_v6",
    "Standard_E4ds_v6",
    "Standard_E8ads_v6",
    "Standard_E8ds_v5",
    "Standard_E8ads_v5",
    "Standard_E8ds_v6",
    "Standard_E8s_v5",
    "Standard_E16ds_v5",
    "Standard_E16ads_v6",
    "Standard_E16ds_v6",
    "Standard_F4s_v2",
    "Standard_F8s_v2",
    "Standard_F16s_v2",
    # Common legacy sizes still seen in metrics tables
    "Standard_E4s_v3",
    "Standard_E8s_v3",
    "Standard_D4s_v3",
    "Standard_D8s_v3",
}


def compose_node_type(node_family: str, vcpus: int, generation: str = "v5") -> str:
    """Build a synthetic ``Standard_{family}{vcpus}s_{gen}`` name.

    Fallback when the allow-list has no family match. Prefer
    ``nearest_allowed_node_type`` for production recommendations.

    Args:
        node_family: Letter family (D/E/F/L); invalid → ``E``.
        vcpus: Desired vCPU count (floored at 4).
        generation: Azure generation suffix (e.g. ``v5``).

    Returns:
        Synthetic SKU string (may not be in ``ALLOWED_AZURE_NODE_TYPES``).
    """
    family = str(node_family).strip().upper()[:1]
    if family not in ("D", "E", "F", "L"):
        family = "E"
    v = max(4, int(vcpus))
    gen = generation if generation.startswith("v") else f"v{generation}"
    return f"Standard_{family}{v}s_{gen}"


def nearest_allowed_node_type(
    node_family: str,
    vcpus: int,
    current_node_type: Optional[str] = None,
) -> str:
    """Pick allow-listed SKU matching family and vCPU size intent.

    Prefer keeping the current SKU when it is already allow-listed and matches
    the target family (avoids churn for no-op shape recommendations). Otherwise
    prefer newer generations (v6/v5) and denser suffixes (ds/ads) among matches.

    Args:
        node_family: Target letter family (D/E/F/L).
        vcpus: Target vCPU size intent.
        current_node_type: Live worker SKU from metrics, if known.

    Returns:
        An allow-listed SKU, or a composed fallback / current SKU when no
        family candidates exist.
    """
    family = str(node_family).strip().upper()[:1]
    v = max(4, int(vcpus))
    if current_node_type and current_node_type in ALLOWED_AZURE_NODE_TYPES:
        cur_f = current_node_type[9:10].upper() if len(current_node_type) > 9 else ""
        if cur_f == family:
            return current_node_type

    candidates = [
        n
        for n in ALLOWED_AZURE_NODE_TYPES
        if f"Standard_{family}" in n
        and f"{family}{v}"
        in n.replace(f"{family}ads", f"{family}").replace(f"{family}ds", f"{family}")
    ]
    if not candidates:
        candidates = [n for n in ALLOWED_AZURE_NODE_TYPES if f"Standard_{family}" in n]
    if candidates:
        candidates.sort(
            key=lambda n: ("ds" in n or "ads" in n, "_v6" in n, "_v5" in n),
            reverse=True,
        )
        return candidates[0]
    return current_node_type or compose_node_type(family, v)
