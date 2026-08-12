"""Compute paired statistics for the GIM ablation manuscript.

Run: backend/.venv/bin/python benchmark/analysis/gim_statistics.py
Reads benchmark/data/reports/nar_ablation/*.json, prints tests + 95% CIs.
"""
import json
from pathlib import Path

import numpy as np
from scipy import stats

BASE = Path(__file__).resolve().parents[2] / "benchmark/data/reports/nar_ablation"


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (round(centre - half, 3), round(centre + half, 3))


def main() -> None:
    abl = json.load(open(BASE / "ablation_report.json"))
    mcr = json.load(open(BASE / "multilingual_contribution_report.json"))

    # ---------- 1. Evidence-item yield: EN track vs combined unique ----------
    mcr_pe = [e for e in mcr["per_entry"]]
    # Report aggregate excludes fused_017 (transient pipeline failure, 0 items both tracks)
    yield_pe = [e for e in mcr_pe if e["entry_id"] != "fused_017"]
    en_items = np.array([e["en_found_items"] for e in yield_pe])
    zh_items = np.array([e["zh_found_items"] for e in yield_pe])
    combined = np.array([e["combined_unique_items"] for e in yield_pe])
    gains = np.array([e["multilingual_gain"] for e in yield_pe])  # ZH-only items
    n = len(yield_pe)

    w_stat, w_p = stats.wilcoxon(gains, alternative="greater")
    r = (w_stat / (n * (n + 1) / 2)) * 2 - 1  # matched-pairs rank-biserial approx
    gain_ci = stats.t.interval(0.95, n - 1, loc=gains.mean(), scale=stats.sem(gains))

    k_gain = int((gains > 0).sum())
    ci_gain = wilson_ci(k_gain, n)
    k_zh = int(sum(1 for e in yield_pe if e["zh_only_field_ids"]))
    ci_zh = wilson_ci(k_zh, n)

    print("=" * 72)
    print("1. Evidence-item yield (ZH-only items), n =", n)
    print(f"   mean EN items={en_items.mean():.2f}  ZH items={zh_items.mean():.2f}  "
          f"mean ZH-only gain={gains.mean():.2f} (+{gains.mean() / en_items.mean() * 100:.1f}%)")
    print(f"   mean combined unique FIELDS={combined.mean():.2f}")
    print(f"   Wilcoxon signed-rank (one-sided, gain>0): W={w_stat:.1f}, p={w_p:.4g}")
    print(f"   Matched-pairs rank-biserial r={r:.3f}")
    print(f"   95% CI of mean gain: [{gain_ci[0]:.2f}, {gain_ci[1]:.2f}]")
    print(f"   entries with ZH-only items: {k_gain}/{n} ({k_gain / n * 100:.1f}%), Wilson 95% CI {ci_gain}")
    print(f"   entries with ZH-only fields: {k_zh}/{n} ({k_zh / n * 100:.1f}%), Wilson 95% CI {ci_zh}")

    # ---------- 2. Field match ablation: EN-only vs dual-track ----------
    abl_pe = {e["entry_id"]: e for e in abl["per_entry"]}
    ids = list(abl_pe.keys())
    en_m = np.array([abl_pe[i]["en_matched_fields"] for i in ids], dtype=float)
    dual_m = np.array([abl_pe[i]["dual_matched_fields"] for i in ids], dtype=float)
    diff = dual_m - en_m
    n2 = len(ids)

    mask = diff != 0
    if mask.sum() > 0:
        w2_stat, w2_p = stats.wilcoxon(diff[mask], alternative="two-sided")
    else:
        w2_stat, w2_p = 0.0, 1.0
    m_ci = stats.t.interval(0.95, n2 - 1, loc=diff.mean(), scale=stats.sem(diff))

    n_gained_entries = int((diff > 0).sum())
    n_lost_entries = int((diff < 0).sum())
    n_swapped = int((diff == 0).sum() and sum(
        1 for e in abl_pe.values()
        if e["dual_matched_fields"] == e["en_matched_fields"] and e["field_improvements"]
    ))
    print("=" * 72)
    print("2. Field-match ablation (paired 0-8 counts), n =", n2)
    print(f"   mean EN={en_m.mean():.2f}  dual={dual_m.mean():.2f}  mean diff={diff.mean():+.3f}")
    print(f"   Wilcoxon signed-rank (two-sided): W={w2_stat:.1f}, p={w2_p:.4g}")
    print(f"   95% CI of mean diff: [{m_ci[0]:+.3f}, {m_ci[1]:+.3f}]")
    print(f"   entries: gained={n_gained_entries}, lost={n_lost_entries}, swapped={n_swapped}")
    print(f"   Wilson 95% CI gained: {wilson_ci(n_gained_entries, n2)}")
    print(f"   Wilson 95% CI lost:   {wilson_ci(n_lost_entries, n2)}")

    # McNemar on per-field discordance across all 8 fields x 30 entries
    b = 0  # en_missed_dual_found
    c = 0  # en_found_dual_missed
    for e in abl_pe.values():
        for imp in e.get("field_improvements", []):
            if imp["improvement"] == "en_missed_dual_found":
                b += 1
            elif imp["improvement"] == "en_found_dual_missed":
                c += 1
    mcnemar_p = stats.binomtest(c, b + c, 0.5, alternative="two-sided").pvalue if b + c else 1.0
    print("   per-field discordance (8 fields x 30 entries):")
    print(f"   dual-only found (b)={b},  EN-only found (c)={c},  McNemar exact p={mcnemar_p:.4g}")

    # ---------- 3. Final-output evidence items (from ablation report) ----------
    en_final = np.array([abl_pe[i]["en_evidence_count"] for i in ids], dtype=float)
    dual_final = np.array([abl_pe[i]["dual_evidence_count"] for i in ids], dtype=float)
    dfinal = dual_final - en_final
    m3 = dfinal != 0
    w3_p = stats.wilcoxon(dfinal[m3], alternative="two-sided").pvalue if m3.sum() else 1.0
    f_ci = stats.t.interval(0.95, n2 - 1, loc=dfinal.mean(), scale=stats.sem(dfinal))
    print("=" * 72)
    print("3. Final-output evidence items/entry: EN-only vs dual-track, n =", n2)
    print(f"   mean EN={en_final.mean():.1f}  dual={dual_final.mean():.1f}  mean diff={dfinal.mean():+.1f}")
    print(f"   Wilcoxon signed-rank (two-sided): p={w3_p:.4g}")
    print(f"   95% CI of mean diff: [{f_ci[0]:+.1f}, {f_ci[1]:+.1f}]")


if __name__ == "__main__":
    main()
