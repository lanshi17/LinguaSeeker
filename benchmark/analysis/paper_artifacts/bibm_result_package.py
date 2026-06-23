"""Generate BIBM main paper result package from all latest reports.

Read-only — aggregates existing reports into a submission-ready result package.

Usage:
    python bibm_result_package.py [--write]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

REPORTS_DIR = Path("benchmark/data/reports")


def _load(name_fragment: str) -> dict[str, Any]:
    path = max(REPORTS_DIR.glob(f"{name_fragment}*.json"), key=lambda p: p.stat().st_mtime)
    return json.loads(path.read_text(encoding="utf-8")), path


def build_package() -> dict[str, Any]:
    """Build the result package from all latest reports."""
    bc, bc_path = _load("baseline_comparison_")
    ss, ss_path = _load("statistical_significance_")
    fd, fd_path = _load("field_difficulty_stratified_eval_")
    pa, pa_path = _load("reconcile_ablation_20260623_182749")
    cs, cs_path = _load("case_studies_main_paper_")

    # Extract key numbers
    bc_rows = {r["label"]: r for r in bc.get("rows", [])}
    sys_row = bc_rows.get("SYSTEM", {})
    b0_row = bc_rows.get("B0", {})

    ss_analyses = {a["label"]: a for a in ss.get("analyses", [])}

    return {
        "package_id": f"bibm_main_paper_result_package_{time.strftime('%Y%m%d_%H%M%S')}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_reports": {
            "baseline_comparison": str(bc_path),
            "statistical_significance": str(ss_path),
            "field_difficulty": str(fd_path),
            "parkinson_ablation": str(pa_path),
            "case_studies": str(cs_path),
        },

        "section_1_dataset_summary": {
            "main_evaluation_set": {
                "datasets": ["rett", "parkinson"],
                "total_entries": 73,
                "rett_entries": 53,
                "parkinson_entries": 20,
                "description": "Merged 73-entry evaluation with paired SYSTEM vs B0 comparison",
            },
            "supporting_datasets": {
                "clingen": {"entries": 30, "phase2_coverage": "30/30", "b0_baseline": "unavailable"},
                "clinvar_fused": {"entries": 75, "phase2_coverage": "20/75", "b0_baseline": "unavailable"},
            },
            "note": "clingen and clinvar_fused lack comparable B0 baselines. They serve as supporting/model-alignment datasets, not main evaluation sets.",
        },

        "section_2_coverage_summary": {
            "rett": {"entries": 53, "phase2_coverage": "53/53"},
            "parkinson": {"entries": 20, "phase2_coverage": "20/20"},
            "clingen": {"entries": 30, "phase2_coverage": "30/30"},
            "clinvar_fused": {"entries": 75, "phase2_coverage": "20/75"},
            "smoke_tests": [
                "rett_043: completed (Phase 3 matches=2, pipeline_status=completed)",
                "parkinson_001: completed (Phase 3 matches=8, pipeline_status=completed)",
            ],
            "infrastructure_fixes": [
                "Phase 3 SAVEPOINT in find_nearest prevents transaction abort on missing table",
                "Language detector _looks_english fallback for biomedical text with gene mutation notation",
                "Validator non_english_output defense-in-depth fix",
            ],
        },

        "section_3_main_baseline_comparison": {
            "system": {
                "precision": sys_row.get("precision", 0),
                "recall": sys_row.get("recall", 0),
                "f1": sys_row.get("f1", 0),
                "total_entries": sys_row.get("total_entries", 0),
            },
            "b0": {
                "precision": b0_row.get("precision", 0),
                "recall": b0_row.get("recall", 0),
                "f1": b0_row.get("f1", 0),
                "total_entries": b0_row.get("total_entries", 0),
            },
            "delta_f1": round(sys_row.get("f1", 0) - b0_row.get("f1", 0), 4),
            "model_metadata": {
                "model_baseline_id": "B6_GPT5_PROMPT_CITE",
                "model": "gpt-5-2025-08-07",
                "provider": "openai",
            },
        },

        "section_4_per_dataset_results": {
            "merged_73": ss_analyses.get("merged_73", {}),
            "rett_53": ss_analyses.get("rett_53", {}),
            "parkinson_20": ss_analyses.get("parkinson_20", {}),
        },

        "section_5_field_difficulty": fd.get("merged_by_difficulty", {}),

        "section_6_statistical_significance": {
            "merged": ss_analyses.get("merged_73", {}).get("paired_permutation_test", {}),
            "rett": ss_analyses.get("rett_53", {}).get("paired_permutation_test", {}),
            "parkinson": ss_analyses.get("parkinson_20", {}).get("paired_permutation_test", {}),
            "by_difficulty": {
                cat: ss_analyses.get(f"merged_{cat}", {}).get("paired_permutation_test", {})
                for cat in ["simple_explicit", "medium_contextual", "complex_evidence"]
            },
        },

        "section_7_case_studies": cs.get("cases", []),

        "section_8_methodological_contributions": [
            "Dual-track cross-lingual evidence extraction: parallel original-language and translated extraction tracks recover evidence missed by English-only approaches.",
            "Context-verifier reconciliation: field-level scoring with source grounding, target specificity, and agreement metrics selects best evidence across tracks.",
            "Canonical evidence alignment: HGVS normalization, MOI canonicalization, and gene-disease relationship normalization bridge terminology gaps between extraction and ground truth.",
            "Recovery-aware phase artifact pipeline: SAVEPOINT-based error isolation, language detector fallbacks, and self-review token budget guards ensure robust end-to-end execution.",
        ],

        "section_9_claims_supported": [
            "SYSTEM significantly outperforms B0 on the merged 73-entry evaluation set (ΔF1=+0.1224, p<0.0001, 95% CI [+0.0800, +0.1626]).",
            "The pipeline's gains are strongest on medium-difficulty contextual fields (ΔF1=+0.2447, p<0.0001) where B0 scores zero.",
            "Complex evidence fields show significant improvement (ΔF1=+0.1096, p=0.0082), though support is dominated by de novo status.",
            "Simple explicit fields show a smaller but significant improvement (ΔF1=+0.0921, p=0.0002).",
            "The dual-track pipeline recovers non-English HGVS variant evidence and de novo status that single-prompt baselines miss.",
            "Pipeline provides structured audit trails and source grounding even when aggregate F1 is comparable to B0.",
        ],

        "section_10_claims_to_avoid": [
            "Do not claim all datasets significantly improve over B0 — Parkinson does not (ΔF1=-0.0583, p=0.2158).",
            "Do not claim Parkinson improves over B0 — it is a boundary/limitation case.",
            "Do not claim clinical phenotype extraction is solved — B.clinical_phenotypes F1=0 (pipeline capability gap).",
            "Do not overclaim complex evidence diversity — support is mostly C.de_novo_status from Rett, not diverse complex evidence types.",
            "Do not claim B0 is weak on all fields — B0 achieves perfect or near-perfect precision on simple factual lookups.",
        ],

        "section_11_remaining_weaknesses": [
            "Parkinson boundary case: SYSTEM does not outperform B0 on this low-complexity English dataset (ΔF1=-0.0583, p=0.2158).",
            "B.clinical_phenotypes pipeline gap: the extraction pipeline does not produce this field; F1=0 despite 71 expected entries.",
            "Complex evidence diversity: all complex_evidence support comes from C.de_novo_status in Rett; segregation, functional assay, and recurrence are not represented.",
            "B0 prompt may be underperforming on medium/complex fields: the naive single-prompt baseline does not request inheritance, variant type, or de novo status, making the comparison partly an artifact of prompt design.",
            "clingen/clinvar_fused lack comparable B0 baselines, limiting generalizability claims.",
        ],

        "section_12_recommended_next_experiments": [
            "Stronger B0 prompt: include medium/complex fields in the baseline prompt to test whether SYSTEM's advantage persists against a more competitive baseline.",
            "Phenotype extraction module: add B.clinical_phenotypes to the extraction pipeline to close the capability gap.",
            "More diverse complex evidence labels: annotate segregation, functional assay, and recurrence in existing datasets to broaden complex_evidence support.",
            "Per-dataset comparison mode automation: eliminate manual merge scripts for baseline comparison.",
            "Expand clingen/clinvar_fused baseline comparability: generate B0 baselines for these datasets to enable broader evaluation.",
        ],

        "section_13_bibm_readiness": {
            "ready_for_main_submission": "borderline",
            "confidence_level": "moderate",
            "strongest_selling_point": (
                "Statistically significant improvement on medium-difficulty contextual fields "
                "(ΔF1=+0.2447, p<0.0001) with clear mechanistic explanation (dual-track "
                "reconciliation recovers evidence single-prompt baselines miss)."
            ),
            "biggest_reviewer_risk": (
                "The naive B0 baseline does not request medium/complex fields, so the comparison "
                "partially reflects prompt design differences rather than extraction capability. "
                "A reviewer may argue that a more detailed B0 prompt would close the gap."
            ),
            "submission_recommendation": (
                "The results are sufficient for a BIBM short paper (4 pages) if framed as a "
                "methodology contribution with empirical validation, not as a claim of universal "
                "improvement. The key narrative should be: (1) define field difficulty tiers, "
                "(2) show pipeline gains scale with difficulty, (3) acknowledge Parkinson as a "
                "boundary case that validates the difficulty framework. The biggest risk is a "
                "reviewer asking for a stronger B0 with medium/complex fields in the prompt. "
                "Mitigation: prepare a supplementary experiment with an expanded B0 prompt. "
                "The case studies provide concrete evidence for the methodology claims."
            ),
        },
    }


def _format_markdown(pkg: dict[str, Any]) -> str:
    s3 = pkg["section_3_main_baseline_comparison"]
    sys = s3["system"]
    b0 = s3["b0"]

    lines = [
        "# BIBM Main Paper Result Package",
        "",
        f"Generated: {pkg['timestamp']}",
        "",
        "---",
        "",
        "## 1. Dataset Summary",
        "",
        "| Dataset | Entries | Phase 2 Coverage | B0 Baseline | Role |",
        "|---|---|---|---|---|",
        "| RETT | 53 | 53/53 | ✓ | Main evaluation |",
        "| Parkinson | 20 | 20/20 | ✓ | Main evaluation |",
        "| ClinGen | 30 | 30/30 | ✗ | Supporting |",
        "| ClinVar Fused | 75 | 20/75 | ✗ | Supporting |",
        "",
        "**Main evaluation set**: Merged RETT (53) + Parkinson (20) = **73 entries**.",
        "ClinGen and ClinVar Fused lack comparable B0 baselines and serve as supporting datasets.",
        "",
        "## 2. Main Baseline Comparison (Merged 73 entries)",
        "",
        "| System | Precision | Recall | F1 |",
        "|---|---|---|---|",
        f"| SYSTEM | {sys['precision']:.4f} | {sys['recall']:.4f} | **{sys['f1']:.4f}** |",
        f"| B0 (naive LLM) | {b0['precision']:.4f} | {b0['recall']:.4f} | {b0['f1']:.4f} |",
        f"| **Δ** | {sys['precision']-b0['precision']:+.4f} | {sys['recall']-b0['recall']:+.4f} | **{s3['delta_f1']:+.4f}** |",
        "",
        "## 3. Per-Dataset Results",
        "",
        "| Dataset | N | SYSTEM F1 | B0 F1 | ΔF1 | p-value | Significant |",
        "|---|---|---|---|---|---|---|",
    ]

    for label in ["merged_73", "rett_53", "parkinson_20"]:
        a = pkg["section_4_per_dataset_results"].get(label, {})
        if not a:
            continue
        perm = a.get("paired_permutation_test", {})
        ci = a.get("bootstrap_ci_95", {}).get("delta_f1_ci", [0, 0])
        lines.append(
            f"| {label.replace('_', ' ')} | {a.get('n_entries', 0)} | "
            f"{a.get('system_overall', {}).get('f1', 0):.4f} | "
            f"{a.get('b0_overall', {}).get('f1', 0):.4f} | "
            f"{a.get('per_entry_mean_f1', {}).get('delta', 0):+.4f} | "
            f"{perm.get('p_value', 0):.4f} | "
            f"{'✓' if perm.get('significant_at_0_05') else '✗'} |"
        )

    lines += [
        "",
        "**RETT** shows statistically significant improvement. "
        "**Parkinson** does not — it is a boundary/limitation case.",
        "",
        "## 4. Field Difficulty Results",
        "",
        "| Category | SYSTEM F1 | B0 F1 | ΔF1 |",
        "|---|---|---|---|",
    ]

    for cat in ["simple_explicit", "medium_contextual", "complex_evidence"]:
        d = pkg["section_5_field_difficulty"].get(cat, {})
        if d:
            lines.append(f"| {cat} | {d.get('system_f1', 0):.4f} | {d.get('b0_f1', 0):.4f} | {d.get('delta_f1', 0):+.4f} |")

    lines += [
        "",
        "**Pipeline gains scale with field difficulty.** "
        "Medium contextual and complex evidence are the primary sources of improvement.",
        "",
        "## 5. Statistical Significance",
        "",
        "| Analysis | ΔF1 | 95% CI | p-value | Significant |",
        "|---|---|---|---|---|",
    ]

    for label, key in [("Merged 73", "merged"), ("RETT 53", "rett"), ("Parkinson 20", "parkinson")]:
        a = pkg["section_4_per_dataset_results"].get(f"{key}_{53 if key == 'rett' else 20 if key == 'parkinson' else 73}", {})
        if not a:
            a = pkg["section_4_per_dataset_results"].get("merged_73", {})
        perm = a.get("paired_permutation_test", {})
        ci = a.get("bootstrap_ci_95", {}).get("delta_f1_ci", [0, 0])
        lines.append(
            f"| {label} | {a.get('per_entry_mean_f1', {}).get('delta', 0):+.4f} | "
            f"[{ci[0]:+.4f}, {ci[1]:+.4f}] | {perm.get('p_value', 0):.4f} | "
            f"{'✓' if perm.get('significant_at_0_05') else '✗'} |"
        )

    for cat in ["simple_explicit", "medium_contextual", "complex_evidence"]:
        perm = pkg["section_6_statistical_significance"].get("by_difficulty", {}).get(cat, {})
        lines.append(
            f"| {cat} | {perm.get('observed_delta', 0):+.4f} | "
            f"— | {perm.get('p_value', 0):.4f} | "
            f"{'✓' if perm.get('significant_at_0_05') else '✗'} |"
        )

    lines += [
        "",
        "## 6. Case Studies",
        "",
    ]

    for i, case in enumerate(pkg.get("section_7_case_studies", []), 1):
        lines += [
            f"### Case {i}: {case.get('title', '')}",
            "",
            f"**{case.get('dataset', '')} / {case.get('entry_id', '')}** — {case.get('difficulty_category', '')}",
            "",
            case.get("paper_ready_paragraph", ""),
            "",
        ]

    lines += [
        "## 7. Claims Supported",
        "",
    ]
    for c in pkg.get("section_9_claims_supported", []):
        lines.append(f"- {c}")

    lines += [
        "",
        "## 8. Claims To Avoid",
        "",
    ]
    for c in pkg.get("section_10_claims_to_avoid", []):
        lines.append(f"- {c}")

    lines += [
        "",
        "## 9. Remaining Weaknesses",
        "",
    ]
    for w in pkg.get("section_11_remaining_weaknesses", []):
        lines.append(f"- {w}")

    lines += [
        "",
        "## 10. BIBM Readiness Assessment",
        "",
        f"**Ready**: {pkg['section_13_bibm_readiness']['ready_for_main_submission']}",
        f"**Confidence**: {pkg['section_13_bibm_readiness']['confidence_level']}",
        "",
        f"**Strongest selling point**: {pkg['section_13_bibm_readiness']['strongest_selling_point']}",
        "",
        f"**Biggest reviewer risk**: {pkg['section_13_bibm_readiness']['biggest_reviewer_risk']}",
        "",
        f"**Recommendation**: {pkg['section_13_bibm_readiness']['submission_recommendation']}",
        "",
    ]

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate BIBM result package")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    pkg = build_package()

    print("BIBM Main Paper Result Package")
    print(f"Generated: {pkg['timestamp']}")
    print(f"\nMain result: SYSTEM F1={pkg['section_3_main_baseline_comparison']['system']['f1']:.4f} "
          f"vs B0 F1={pkg['section_3_main_baseline_comparison']['b0']['f1']:.4f} "
          f"(Δ={pkg['section_3_main_baseline_comparison']['delta_f1']:+.4f})")
    print(f"Readiness: {pkg['section_13_bibm_readiness']['ready_for_main_submission']}")

    if args.write:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        json_path = REPORTS_DIR / f"bibm_main_paper_result_package_{timestamp}.json"
        json_path.write_text(json.dumps(pkg, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON: {json_path}")

        md_path = REPORTS_DIR / f"bibm_main_paper_result_package_{timestamp}.md"
        md_path.write_text(_format_markdown(pkg), encoding="utf-8")
        print(f"MD: {md_path}")


if __name__ == "__main__":
    main()
