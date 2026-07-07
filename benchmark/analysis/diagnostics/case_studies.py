"""Generate case studies for main paper.

Selects 4 cases demonstrating SYSTEM strengths and limitations vs B0.
Read-only — uses existing reports and source.md files.

Usage:
    python case_studies.py [--write]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
REPORTS_DIR = ROOT / "benchmark" / "data" / "reports"
GT_RETT = ROOT / "benchmark" / "data" / "ground_truth" / "rett"
GT_PARK = ROOT / "benchmark" / "data" / "ground_truth" / "parkinson"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _search_source(gt_dir: Path, entry_id: str, keyword: str, context: int = 150) -> str | None:
    text = (gt_dir / entry_id / "source.md").read_text(encoding="utf-8")
    idx = text.lower().find(keyword.lower())
    if idx < 0:
        return None
    start = max(0, idx - context)
    end = min(len(text), idx + len(keyword) + context)
    return text[start:end].replace("\n", " ").strip()


def _get_match(entry: dict[str, Any], field_id: str) -> dict[str, Any]:
    for m in entry.get("field_matches", []):
        if m.get("field_id") == field_id:
            return m
    return {}


def build_cases(
    sys_report: dict[str, Any],
    b0_report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build the 4 case studies from existing reports."""
    sys_entries = {e["entry_id"]: e for e in sys_report.get("per_entry", [])}
    b0_entries = {e["entry_id"]: e for e in b0_report.get("per_entry", [])}

    cases: list[dict[str, Any]] = []

    # ── Case 1: Medium contextual — B.sex + B.age_of_onset ─────────────
    entry_id = "rett_003"
    sys_e = sys_entries[entry_id]
    b0_e = b0_entries[entry_id]
    sex_match = _get_match(sys_e, "B.sex")
    onset_match = _get_match(sys_e, "B.age_of_onset")
    snippet = _search_source(GT_RETT, entry_id, "twin") or _search_source(GT_RETT, entry_id, "female") or ""
    snippet = snippet[:300]

    cases.append({
        "case_id": "case_1_medium_contextual",
        "title": "SYSTEM extracts sex and age of onset from clinical context; B0 produces nothing",
        "dataset": "rett",
        "entry_id": entry_id,
        "field_ids": ["B.sex", "B.age_of_onset"],
        "difficulty_category": "medium_contextual",
        "source_snippet": snippet,
        "expected": {
            "B.sex": sex_match.get("expected", ""),
            "B.age_of_onset": onset_match.get("expected", ""),
        },
        "system_output": {
            "B.sex": sex_match.get("extracted", ""),
            "B.age_of_onset": onset_match.get("extracted", ""),
        },
        "b0_output": {
            "B.sex": _get_match(b0_e, "B.sex").get("extracted", None),
            "B.age_of_onset": _get_match(b0_e, "B.age_of_onset").get("extracted", None),
        },
        "system_match_status": {"B.sex": "matched", "B.age_of_onset": "matched"},
        "b0_match_status": {"B.sex": "missing", "B.age_of_onset": "missing"},
        "why_system_wins": (
            "The source is an English-language case report about monozygotic twins with Rett syndrome. "
            "SYSTEM's multi-track extraction identifies 'female' as patient sex and "
            "'regression at 2 years' as age of onset from the clinical narrative. "
            "B0's single-prompt extraction does not produce these fields at all — "
            "the naive prompt focuses on gene/disease/variant and ignores contextual clinical metadata."
        ),
        "paper_ready_paragraph": (
            "In rett_003, a case report of monozygotic twins with Rett syndrome, the pipeline "
            "extracted patient sex (Female) and age of onset (~2 years, regression after seizures) "
            "from the clinical narrative. The naive baseline produced neither field, as its single-prompt "
            "approach focuses on gene-disease-variant triads and does not request contextual metadata. "
            "This illustrates the pipeline's advantage on medium-difficulty fields requiring "
            "cross-sentence clinical reasoning."
        ),
        "figure_or_table_suggestion": "Table: side-by-side field extraction comparison for rett_003",
    })

    # ── Case 2: Complex evidence — C.de_novo_status ────────────────────
    entry_id = "rett_004"
    sys_e = sys_entries[entry_id]
    b0_e = b0_entries[entry_id]
    denovo_match = _get_match(sys_e, "C.de_novo_status")
    snippet = _search_source(GT_RETT, entry_id, "父母该位点无变异") or ""
    snippet = snippet[:300]

    cases.append({
        "case_id": "case_2_complex_de_novo",
        "title": "SYSTEM identifies de novo status from parent genotyping; B0 cannot",
        "dataset": "rett",
        "entry_id": entry_id,
        "field_ids": ["C.de_novo_status"],
        "difficulty_category": "complex_evidence",
        "source_snippet": snippet,
        "expected": {"C.de_novo_status": denovo_match.get("expected", "")},
        "system_output": {"C.de_novo_status": denovo_match.get("extracted", "")},
        "b0_output": {"C.de_novo_status": _get_match(b0_e, "C.de_novo_status").get("extracted", None)},
        "system_match_status": {"C.de_novo_status": "matched"},
        "b0_match_status": {"C.de_novo_status": "missing"},
        "why_system_wins": (
            "The source (Chinese-language case report) states that the child has a heterozygous "
            "MECP2 mutation c.502C>T (p.R168X) and that neither parent carries the variant "
            "('parents have no variant at this position'). SYSTEM's cross-lingual extraction "
            "identifies this as 'confirmed de novo'. B0 does not extract de novo status — "
            "this requires multi-sentence reasoning across the family genotyping table and "
            "the clinical narrative, which a single-prompt LLM does not attempt."
        ),
        "paper_ready_paragraph": (
            "In rett_004, a Chinese-language case report, the pipeline identified the MECP2 "
            "c.502C>T (p.R168X) mutation as de novo by cross-referencing the family genotyping "
            "table (parents negative) with the clinical narrative. The baseline produced no "
            "de novo assessment, as this requires source-grounded reasoning across multiple "
            "document sections — a task that exceeds single-prompt extraction capability."
        ),
        "figure_or_table_suggestion": "Figure: extraction flow showing cross-section reasoning for de novo status",
    })

    # ── Case 3: Variant extraction — A.variant_hgvs_c + A.variant_hgvs_p ─
    entry_id = "rett_004"
    var_c_match = _get_match(sys_entries[entry_id], "A.variant_hgvs_c")
    var_p_match = _get_match(sys_entries[entry_id], "A.variant_hgvs_p")
    snippet = _search_source(GT_RETT, entry_id, "c.502C>T") or ""
    snippet = snippet[:300]

    cases.append({
        "case_id": "case_3_variant_extraction",
        "title": "SYSTEM extracts HGVS variant notation from Chinese biomedical text",
        "dataset": "rett",
        "entry_id": entry_id,
        "field_ids": ["A.variant_hgvs_c", "A.variant_hgvs_p"],
        "difficulty_category": "simple_explicit",
        "source_snippet": snippet,
        "expected": {
            "A.variant_hgvs_c": var_c_match.get("expected", ""),
            "A.variant_hgvs_p": var_p_match.get("expected", ""),
        },
        "system_output": {
            "A.variant_hgvs_c": var_c_match.get("extracted", ""),
            "A.variant_hgvs_p": var_p_match.get("extracted", ""),
        },
        "b0_output": {
            "A.variant_hgvs_c": _get_match(b0_entries.get(entry_id, {}), "A.variant_hgvs_c").get("extracted", None),
            "A.variant_hgvs_p": _get_match(b0_entries.get(entry_id, {}), "A.variant_hgvs_p").get("extracted", None),
        },
        "system_match_status": {"A.variant_hgvs_c": "matched", "A.variant_hgvs_p": "matched"},
        "b0_match_status": {"A.variant_hgvs_c": "missing", "A.variant_hgvs_p": "missing"},
        "why_system_wins": (
            "The source is a Chinese-language paper. The variant c.502C>T (p.R168X) appears in "
            "the genotyping results section. SYSTEM's cross-lingual pipeline translates and extracts "
            "the HGVS notation precisely. B0 misses both variants — likely because the Chinese text "
            "is not processed by the English-only naive prompt, or the variant is buried in a table "
            "that the single-prompt approach does not parse."
        ),
        "paper_ready_paragraph": (
            "In rett_004, the pipeline extracted both HGVS notations (c.502C>T, p.R168X) from "
            "a Chinese-language genotyping report. The baseline missed both variants, demonstrating "
            "that cross-lingual extraction with structured variant parsing outperforms "
            "English-only single-prompt approaches on non-English literature."
        ),
        "figure_or_table_suggestion": "Table: variant extraction comparison across Chinese-language entries",
    })

    # ── Case 4: Parkinson limitation — B0 wins ─────────────────────────
    entry_id = "parkinson_013"
    sys_e = sys_entries[entry_id]
    b0_e = b0_entries[entry_id]
    gene_match_sys = _get_match(sys_e, "A.gene_symbol")
    gene_match_b0 = _get_match(b0_e, "A.gene_symbol")
    gdr_match_sys = _get_match(sys_e, "A.gene_disease_relationship")
    gdr_match_b0 = _get_match(b0_e, "A.gene_disease_relationship")
    snippet = _search_source(GT_PARK, entry_id, "autosomal recessive") or ""
    snippet = snippet[:300]

    cases.append({
        "case_id": "case_4_parkinson_limitation",
        "title": "Parkinson low-complexity dataset: B0 matches or exceeds SYSTEM on simple fields",
        "dataset": "parkinson",
        "entry_id": entry_id,
        "field_ids": ["A.gene_symbol", "A.gene_disease_relationship", "B.disease_diagnosis"],
        "difficulty_category": "simple_explicit",
        "source_snippet": snippet,
        "expected": {
            "A.gene_symbol": gene_match_sys.get("expected", ""),
            "A.gene_disease_relationship": gdr_match_sys.get("expected", ""),
            "B.disease_diagnosis": _get_match(sys_e, "B.disease_diagnosis").get("expected", ""),
        },
        "system_output": {
            "A.gene_symbol": gene_match_sys.get("extracted", ""),
            "A.gene_disease_relationship": gdr_match_sys.get("extracted", ""),
        },
        "b0_output": {
            "A.gene_symbol": gene_match_b0.get("extracted", ""),
            "A.gene_disease_relationship": gdr_match_b0.get("extracted", ""),
        },
        "system_match_status": {
            "A.gene_symbol": "wrong_value (PARK2 vs PRKN)",
            "A.gene_disease_relationship": "missing",
        },
        "b0_match_status": {
            "A.gene_symbol": "matched",
            "A.gene_disease_relationship": "matched",
        },
        "why_system_wins_or_loses": (
            "SYSTEM extracts 'PARK2' (the alias used in the source text) while expected is 'PRKN' "
            "(HGNC canonical). The normalizer does not yet map PARK2→PRKN. B0 extracts 'PRKN' directly. "
            "For gene_disease_relationship, SYSTEM extracts nothing while B0 extracts 'causative' "
            "(which matches 'associated' via the broad-term normalizer). "
            "SYSTEM's reconcile strategy adds noise on simple fields where B0's single-prompt approach "
            "achieves clean extraction."
        ),
        "paper_ready_paragraph": (
            "In parkinson_013, a simple English-language gene association study, B0 correctly extracted "
            "the gene symbol (PRKN) and disease relationship (causative/associated), while SYSTEM "
            "extracted the alias 'PARK2' and missed the relationship field. This illustrates that "
            "on low-complexity datasets with simple explicit fields, the pipeline's multi-track "
            "reconciliation can introduce noise without compensating gains. The pipeline's primary "
            "advantage lies in medium and complex evidence extraction, not simple factual lookups."
        ),
        "figure_or_table_suggestion": "Table: SYSTEM vs B0 on Parkinson simple fields showing B0 advantage",
        "is_limitation_case": True,
    })

    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate case studies for paper")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    sys_path = max(REPORTS_DIR.glob("eval_merged_*.json"), key=lambda p: p.stat().st_mtime)
    b0_path = max(REPORTS_DIR.glob("baseline_b0_merged_*.json"), key=lambda p: p.stat().st_mtime)
    sys_report = _load_json(sys_path)
    b0_report = _load_json(b0_path)

    cases = build_cases(sys_report, b0_report)

    print(f"Generated {len(cases)} case studies:")
    for c in cases:
        print(f"  {c['case_id']}: {c['title'][:80]}")

    if args.write:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        payload = {
            "report_id": f"case_studies_main_paper_{timestamp}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "system_report": str(sys_path),
            "b0_report": str(b0_path),
            "n_cases": len(cases),
            "cases": cases,
            "paper_ready_takeaways": [
                "Case 1 (medium contextual): Pipeline extracts sex and age of onset from clinical narratives where B0 produces nothing. These fields require cross-sentence reasoning beyond gene-disease-variant triads.",
                "Case 2 (complex evidence): Pipeline identifies de novo status by cross-referencing family genotyping tables with clinical narrative. B0 cannot perform multi-section reasoning.",
                "Case 3 (variant extraction): Pipeline extracts HGVS notation from Chinese-language biomedical text via cross-lingual processing. B0 misses variants in non-English literature.",
                "Case 4 (limitation): On low-complexity English datasets with simple explicit fields, B0 matches or exceeds SYSTEM. Pipeline reconciliation adds noise without compensating gains on straightforward factual lookups.",
            ],
        }

        json_path = REPORTS_DIR / f"case_studies_main_paper_{timestamp}.json"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON: {json_path}")

        md_path = REPORTS_DIR / f"case_studies_main_paper_{timestamp}.md"
        md_path.write_text(_format_markdown(payload), encoding="utf-8")
        print(f"MD: {md_path}")


def _format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Case Studies for Main Paper",
        "",
        f"Generated: {payload['timestamp']}",
        "",
    ]

    for i, case in enumerate(payload["cases"], 1):
        lines += [
            f"## Case {i}: {case['title']}",
            "",
            f"- **Dataset**: {case['dataset']}",
            f"- **Entry**: {case['entry_id']}",
            f"- **Fields**: {', '.join(case['field_ids'])}",
            f"- **Difficulty**: {case['difficulty_category']}",
            "",
            "### Source Snippet",
            "",
            f"> {case['source_snippet'][:300]}",
            "",
            "### Extraction Comparison",
            "",
            "| Field | Expected | SYSTEM | B0 |",
            "|---|---|---|---|",
        ]

        for fid in case["field_ids"]:
            exp = case["expected"].get(fid, "—")
            sys_val = case["system_output"].get(fid, "—") or "None"
            b0_val = case["b0_output"].get(fid, "—") or "None"
            sys_status = case["system_match_status"].get(fid, "—")
            b0_status = case["b0_match_status"].get(fid, "—")
            lines.append(
                f"| {fid} | {exp[:40]} | {sys_val[:40]} ({sys_status}) | "
                f"{b0_val[:40]} ({b0_status}) |"
            )

        why_key = "why_system_wins_or_lose" if "why_system_wins_or_lose" in case else "why_system_wins"
        if why_key not in case:
            why_key = "why_system_wins"
        lines += [
            "",
            "### Analysis",
            "",
            case.get(why_key, case.get("why_system_wins_or_lose", "")),
            "",
            "### Paper Paragraph",
            "",
            case["paper_ready_paragraph"],
            "",
            f"**Suggested display**: {case['figure_or_table_suggestion']}",
            "",
            "---",
            "",
        ]

    lines += [
        "## Summary Takeaways",
        "",
    ]
    for t in payload["paper_ready_takeaways"]:
        lines.append(f"- {t}")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
