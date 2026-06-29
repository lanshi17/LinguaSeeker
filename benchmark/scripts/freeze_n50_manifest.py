"""Freeze the N=50 stratified comparison/ablation manifest.

Implements the sampling strategy from
``docs/active/2026-06-29-bibm-n50-comparison-ablation-design.md``:

- Stratified sampling by ``source_dataset`` with pre-declared quotas.
- Within each stratum, balance by field-count quartile, D-I family
  expected-field presence, and previous full-run found rate.
- Exclude the 5-entry workflow-selection pilot IDs.
- Fixed seed for reproducibility.

Usage::

    cd backend && uv run python -m benchmark.scripts.freeze_n50_manifest
"""
from __future__ import annotations

import hashlib
import json
import statistics
import time
from pathlib import Path

from benchmark.core.paths import REPORTS_ROOT

# ── Constants from the design doc ──────────────────────────────────────

SEED = "lingua-seeker-bibm-n50-20260629"
POOL_REPORT = REPORTS_ROOT / "eval_unified_merged_b8_20260627.json"
MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "benchmark" / "data" / "manifests"
    / "unified_b8_n50_comparison_20260629.json"
)

# Recommended N=50 allocation from the design doc.
QUOTAS: dict[str, int] = {
    "clingen": 5,
    "clinvar_fused": 23,
    "parkinson": 6,
    "rett": 16,
}

# 5-entry workflow-selection pilot IDs (from b8_business_retest reports).
PILOT_IDS: frozenset[str] = frozenset({
    "gs_054", "gs_058", "gs_061", "gs_074", "gs_098",
})

# Field IDs in the D-I (gene-disease relationship / disease diagnosis) family.
_DI_PREFIXES = ("A.gene_disease", "B.disease", "D.")


def _deterministic_sort_key(entry: dict) -> str:
    """Deterministic sort key — entry_id is globally unique and stable."""
    return entry["entry_id"]


def _has_di_family(entry: dict) -> bool:
    """Whether the entry contains D-I family expected fields."""
    field_ids = {f["field_id"] for f in entry.get("field_matches", [])}
    return any(fid.startswith(_DI_PREFIXES) for fid in field_ids)


def _field_count_quartile(entry: dict, quartile_edges: list[float]) -> int:
    """Assign field-count quartile (0-3) using pre-computed edges."""
    fc = len(entry.get("field_matches", []))
    for i, edge in enumerate(quartile_edges):
        if fc <= edge:
            return i
    return len(quartile_edges)


def _seeded_rng(seed: str) -> float:
    """Deterministic pseudo-random float in [0, 1) from a string seed."""
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(h[:16], 16) / float(1 << 64)


def _compute_quartile_edges(values: list[int]) -> list[float]:
    """Compute quartile edges (Q1, Q2, Q3) for field counts."""
    if len(values) < 4:
        return [float(max(values))] if values else [0.0]
    q1 = statistics.quantiles(values, n=4, method="inclusive")[0]
    q2 = statistics.quantiles(values, n=4, method="inclusive")[1]
    q3 = statistics.quantiles(values, n=4, method="inclusive")[2]
    return [q1, q2, q3]


def _sample_stratum(
    entries: list[dict],
    quota: int,
    seed: str,
) -> list[dict]:
    """Sample ``quota`` entries from a single source stratum.

    Balances across field-count quartile × D-I family substrata, then
    selects evenly across the found-rate range within each substratum.
    """
    if len(entries) <= quota:
        return sorted(entries, key=_deterministic_sort_key)

    field_counts = [len(e.get("field_matches", [])) for e in entries]
    edges = _compute_quartile_edges(field_counts)

    # Build substrata: (quartile, has_di) -> entries sorted by found_rate
    substrata: dict[tuple[int, bool], list[dict]] = {}
    for e in entries:
        q = _field_count_quartile(e, edges)
        di = _has_di_family(e)
        key = (q, di)
        substrata.setdefault(key, []).append(e)

    # Sort each substratum by found_rate, then by deterministic key
    for key in substrata:
        substrata[key].sort(key=lambda e: (e.get("found_rate", 0), _deterministic_sort_key(e)))

    # Allocate quota proportionally across substrata (largest remainder method)
    num_substrata = len(substrata)
    base = quota // num_substrata
    remainder = quota % num_substrata

    # Sort substrata by size descending for remainder allocation
    substratum_keys = sorted(substrata.keys(), key=lambda k: len(substrata[k]), reverse=True)

    selected: list[dict] = []
    for i, key in enumerate(substratum_keys):
        pool = substrata[key]
        alloc = base + (1 if i < remainder else 0)
        alloc = min(alloc, len(pool))

        if alloc == 0:
            continue

        # Evenly sample across the found_rate range
        if len(pool) <= alloc:
            selected.extend(pool)
        else:
            # Pick entries at evenly spaced indices across the sorted pool
            step = len(pool) / alloc
            indices = [int(i * step) for i in range(alloc)]
            # Deduplicate and fill if needed
            indices = sorted(set(indices))
            while len(indices) < alloc:
                for j in range(len(pool)):
                    if j not in indices:
                        indices.append(j)
                        break
            indices = sorted(indices)[:alloc]
            selected.extend(pool[j] for j in indices)

    # If we under-selected (rounding), fill from the best remaining
    if len(selected) < quota:
        remaining = [e for e in entries if e not in selected]
        remaining.sort(key=lambda e: (_deterministic_sort_key(e)))
        for e in remaining:
            if len(selected) >= quota:
                break
            selected.append(e)

    # If we over-selected (rounding), trim deterministically
    if len(selected) > quota:
        selected.sort(key=lambda e: (_deterministic_sort_key(e)))
        selected = selected[:quota]

    selected.sort(key=_deterministic_sort_key)
    return selected


def freeze_manifest() -> dict:
    """Generate and write the frozen N=50 manifest."""
    pool_data = json.loads(POOL_REPORT.read_text(encoding="utf-8"))
    all_entries = pool_data["per_entry"]

    # Exclude pilot IDs
    eligible = [e for e in all_entries if e["entry_id"] not in PILOT_IDS]

    # Group by source_dataset
    by_source: dict[str, list[dict]] = {}
    for e in eligible:
        by_source.setdefault(e["source_dataset"], []).append(e)

    # Sample each stratum
    selected_entries: list[dict] = []
    stratum_summaries: list[dict] = []
    for source in sorted(QUOTAS.keys()):
        entries = by_source.get(source, [])
        entries.sort(key=_deterministic_sort_key)
        quota = QUOTAS[source]
        sampled = _sample_stratum(entries, quota, SEED)

        for e in sampled:
            selected_entries.append({
                "entry_id": e["entry_id"],
                "source_dataset": e["source_dataset"],
                "original_entry_id": e.get("original_entry_id", ""),
                "gene_symbol": e.get("gene_symbol", ""),
                "classification": e.get("classification", ""),
                "moi": e.get("moi", ""),
                "field_count": len(e.get("field_matches", [])),
                "found_rate": e.get("found_rate", 0),
                "has_di_family": _has_di_family(e),
            })

        field_counts = [len(e.get("field_matches", [])) for e in entries]
        found_rates = [e.get("found_rate", 0) for e in entries]
        stratum_summaries.append({
            "source_dataset": source,
            "pool_size": len(entries),
            "quota": quota,
            "selected": len(sampled),
            "field_count_range": [min(field_counts), max(field_counts)] if field_counts else [0, 0],
            "found_rate_range": [round(min(found_rates), 4), round(max(found_rates), 4)] if found_rates else [0, 0],
        })

    selected_entries.sort(key=lambda e: e["entry_id"])

    manifest = {
        "manifest_id": "unified_b8_n50_comparison_20260629",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "design_doc": "docs/active/2026-06-29-bibm-n50-comparison-ablation-design.md",
        "seed": SEED,
        "pool_report": str(POOL_REPORT),
        "pool_total": len(all_entries),
        "excluded_pilot_ids": sorted(PILOT_IDS),
        "eligible_after_exclusion": len(eligible),
        "target_n": 50,
        "actual_n": len(selected_entries),
        "strata": stratum_summaries,
        "entries": selected_entries,
    }

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    manifest = freeze_manifest()
    print(f"Manifest written to: {MANIFEST_PATH}")
    print(f"Target N=50, actual N={manifest['actual_n']}")
    for s in manifest["strata"]:
        print(f"  {s['source_dataset']}: pool={s['pool_size']}, "
              f"quota={s['quota']}, selected={s['selected']}")
    print(f"Excluded pilot IDs: {manifest['excluded_pilot_ids']}")
