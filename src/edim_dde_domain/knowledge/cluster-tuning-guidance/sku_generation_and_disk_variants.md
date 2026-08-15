# Azure SKU generation and disk variants

Treat `ds`, `ads`, and newer SKU generations as implementation choices after
the workload resource shape is established—not as automatic upgrades.

Guidance:
- Prefer a newer allow-listed generation when it preserves the required
  family/vCPU/memory shape and platform policy permits it.
- `d`/`e` identify the broad compute-memory family; `s` denotes premium-storage
  capability; `a` variants may have a different processor platform.
- Do not move to DS/ADS solely because a prior job did. Require compatibility
  and relevant storage/price/performance evidence supplied by the platform.
- Never invent benchmark or cost claims that are absent from inputs.

Actions may include choosing a newer generation, changing a disk-capability
variant, or retaining the current variant. Index actions by semantic direction,
not by a fixed scenario label.
Keywords: Azure VM SKU, generation, v5, v6, DS, ADS, premium storage,
compatibility, allow-list.
