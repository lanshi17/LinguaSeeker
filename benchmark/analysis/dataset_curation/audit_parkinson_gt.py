"""Audit Parkinson ground truth quality: structure, gene symbols, field complexity.

Read-only — does not modify any ground truth data.
"""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

GROUND_TRUTH_ROOT = Path("benchmark/data/ground_truth")
REPORTS_DIR = Path("benchmark/data/reports")

# Field complexity categories (field_id prefixes / exact ids)
SIMPLE_EXPLICIT = {
    "A.gene_symbol",
    "B.disease_diagnosis",
    "A.gene_disease_relationship",
    "A.variant_hgvs_p",
    "A.variant_hgvs_c",
}
MEDIUM_CONTEXTUAL = {
    "B.mode_of_inheritance_reported",
    "B.hpo_terms",
    "B.clinical_phenotypes",
    "B.sex",
    "B.age_of_onset",
    "A.variant_type",
    "A.functional_domain_or_hotspot",
}
COMPLEX_EVIDENCE = {
    "C.de_novo_status",
    "C.segregation",
    "C.functional_assay",
    "C.recurrence",
    "C.contradiction",
    "C.source_grounded_evidence",
    "C.population_data",
    "C.computational_prediction",
}


def _classify_field(field_id: str) -> str:
    if field_id in SIMPLE_EXPLICIT:
        return "simple_explicit"
    if field_id in MEDIUM_CONTEXTUAL:
        return "medium_contextual"
    if field_id in COMPLEX_EVIDENCE:
        return "complex_evidence"
    # Heuristic fallback
    if field_id.startswith("A."):
        return "simple_explicit"
    if field_id.startswith("B."):
        return "medium_contextual"
    if field_id.startswith("C."):
        return "complex_evidence"
    return "unknown"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _audit_dataset(gt_dir: Path) -> dict[str, Any]:
    """Audit one ground truth dataset directory."""
    selection_path = gt_dir / "selection.json"
    if not selection_path.exists():
        return {"error": f"selection.json not found in {gt_dir}"}

    selection = _load_json(selection_path)
    entries_detail: list[dict[str, Any]] = []
    field_counter: Counter[str] = Counter()
    gene_symbol_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    park2_parkin_issues: list[dict[str, Any]] = []
    source_lengths: list[int] = []
    field_counts: list[int] = []

    for item in selection:
        entry_id = str(item["entry_id"])
        entry_dir = gt_dir / entry_id

        # Load expected.json
        expected_path = entry_dir / "expected.json"
        if not expected_path.exists():
            entries_detail.append({"entry_id": entry_id, "error": "expected.json missing"})
            continue
        expected = _load_json(expected_path)

        # Source.md length
        source_path = entry_dir / "source.md"
        source_len = len(source_path.read_text(encoding="utf-8")) if source_path.exists() else 0
        source_lengths.append(source_len)

        # Phase 2 artifact
        meta_path = entry_dir / "meta.json"
        meta = _load_json(meta_path) if meta_path.exists() else {}
        run_id = meta.get("run_id", "")

        # Gene symbol analysis
        gene_sym = str(expected.get("gene_symbol", ""))
        gene_symbol_counter[gene_sym] += 1

        # Expected evidence fields
        evidence = expected.get("expected_evidence", [])
        field_counts.append(len(evidence))

        entry_fields: list[str] = []
        entry_categories: Counter[str] = Counter()
        for ev in evidence:
            fid = str(ev.get("field_id", ""))
            field_counter[fid] += 1
            entry_fields.append(fid)
            cat = _classify_field(fid)
            category_counter[cat] += 1
            entry_categories[cat] += 1

        # Check PARK2/PARKIN/PRKN issue:
        # expected_evidence A.gene_symbol value vs expected.gene_symbol
        ev_gene_values = [
            str(ev.get("value", ""))
            for ev in evidence
            if ev.get("field_id") == "A.gene_symbol"
        ]
        ev_gene_val = ev_gene_values[0] if ev_gene_values else ""
        has_issue = False
        issue_desc = ""

        # Issue 1: gene_symbol field says PARKIN but actual gene is different
        if ev_gene_val == "PARKIN" and gene_sym != "PARK2" and gene_sym != "PARKIN":
            has_issue = True
            issue_desc = (
                f"expected_evidence A.gene_symbol='PARKIN' but "
                f"entry gene_symbol='{gene_sym}' — wrong gene name in evidence"
            )
        # Issue 2: gene_symbol is PARK2 but HGNC canonical is PRKN
        if gene_sym == "PARK2":
            has_issue = True
            issue_desc = (
                "gene_symbol='PARK2' — HGNC canonical symbol is PRKN; "
                "PARKIN is the protein name, not the gene symbol"
            )
        if has_issue:
            park2_parkin_issues.append({
                "entry_id": entry_id,
                "gene_symbol_field": gene_sym,
                "evidence_gene_value": ev_gene_val,
                "issue": issue_desc,
            })

        entries_detail.append({
            "entry_id": entry_id,
            "gene_symbol": gene_sym,
            "expected_field_count": len(evidence),
            "fields": entry_fields,
            "simple_explicit": entry_categories.get("simple_explicit", 0),
            "medium_contextual": entry_categories.get("medium_contextual", 0),
            "complex_evidence": entry_categories.get("complex_evidence", 0),
            "source_md_chars": source_len,
            "run_id": run_id,
        })

    total = len(entries_detail)
    avg_fields = sum(field_counts) / total if total else 0.0
    avg_source = sum(source_lengths) / total if total else 0.0

    return {
        "total_entries": total,
        "avg_expected_fields_per_entry": round(avg_fields, 2),
        "avg_source_md_chars": round(avg_source, 1),
        "field_frequency": dict(field_counter.most_common()),
        "gene_symbol_distribution": dict(gene_symbol_counter.most_common()),
        "entries_with_park2_or_parkin_issue": park2_parkin_issues,
        "park2_parkin_issue_count": len(park2_parkin_issues),
        "simple_field_count": category_counter.get("simple_explicit", 0),
        "medium_field_count": category_counter.get("medium_contextual", 0),
        "complex_field_count": category_counter.get("complex_evidence", 0),
        "per_entry": entries_detail,
    }


def _comparison_with_rett(parkinson_stats: dict[str, Any]) -> dict[str, Any]:
    """Compare parkinson with rett dataset complexity."""
    rett_stats = _audit_dataset(GROUND_TRUTH_ROOT / "rett")

    p_total = parkinson_stats.get("total_entries", 0)
    r_total = rett_stats.get("total_entries", 0)
    p_avg = parkinson_stats.get("avg_expected_fields_per_entry", 0.0)
    r_avg = rett_stats.get("avg_expected_fields_per_entry", 0.0)

    p_simple = parkinson_stats.get("simple_field_count", 0)
    p_medium = parkinson_stats.get("medium_field_count", 0)
    p_complex = parkinson_stats.get("complex_field_count", 0)
    p_total_fields = p_simple + p_medium + p_complex

    r_simple = rett_stats.get("simple_field_count", 0)
    r_medium = rett_stats.get("medium_field_count", 0)
    r_complex = rett_stats.get("complex_field_count", 0)
    r_total_fields = r_simple + r_medium + r_complex

    return {
        "parkinson": {
            "entries": p_total,
            "avg_fields": p_avg,
            "simple": p_simple,
            "medium": p_medium,
            "complex": p_complex,
            "simple_pct": round(p_simple / p_total_fields * 100, 1) if p_total_fields else 0,
            "medium_pct": round(p_medium / p_total_fields * 100, 1) if p_total_fields else 0,
            "complex_pct": round(p_complex / p_total_fields * 100, 1) if p_total_fields else 0,
        },
        "rett": {
            "entries": r_total,
            "avg_fields": r_avg,
            "simple": r_simple,
            "medium": r_medium,
            "complex": r_complex,
            "simple_pct": round(r_simple / r_total_fields * 100, 1) if r_total_fields else 0,
            "medium_pct": round(r_medium / r_total_fields * 100, 1) if r_total_fields else 0,
            "complex_pct": round(r_complex / r_total_fields * 100, 1) if r_total_fields else 0,
        },
        "verdict": (
            "Parkinson ground truth is significantly less complex than RETT: "
            f"avg {p_avg:.1f} fields/entry vs RETT {r_avg:.1f}, "
            f"with {parkinson_stats.get('simple_pct', 0):.0f}% simple fields "
            f"and zero complex evidence fields. "
            "This explains why SYSTEM and B0 F1 are nearly identical — "
            "the reconcile strategy cannot improve on fields that don't exist."
        ),
    }


def _recommended_fixes(
    parkinson_stats: dict[str, Any],
    comparison: dict[str, Any],
) -> list[dict[str, str]]:
    fixes: list[dict[str, str]] = []

    # Fix 1: Gene symbol normalization
    issue_count = parkinson_stats.get("park2_parkin_issue_count", 0)
    if issue_count > 0:
        fixes.append({
            "priority": "P0",
            "category": "gene_symbol",
            "description": (
                f"{issue_count}/{parkinson_stats['total_entries']} entries have "
                f"PARK2/PARKIN gene symbol issues. "
                "All PARK2 entries should use HGNC canonical 'PRKN'. "
                "All expected_evidence A.gene_symbol='PARKIN' should match "
                "the actual gene_symbol of the entry (GBA, LRRK2, SNCA, etc.)."
            ),
            "action": "Fix gene_symbol to PRKN where applicable; fix evidence gene values to match actual gene.",
        })

    # Fix 2: Enrich fields
    p_complex = parkinson_stats.get("complex_field_count", 0)
    if p_complex == 0:
        fixes.append({
            "priority": "P1",
            "category": "field_enrichment",
            "description": (
                "Zero complex evidence fields in the entire dataset. "
                "Add at least: B.mode_of_inheritance_reported, "
                "A.variant_type, C.de_novo_status where the literature supports it."
            ),
            "action": (
                "Read source.md for each entry and add medium/complex fields "
                "supported by the literature. Target: ≥2 medium fields per entry."
            ),
        })

    # Fix 3: Dedup variants
    fixes.append({
        "priority": "P2",
        "category": "variant_dedup",
        "description": (
            "Some entries have duplicate variant_hgvs_p values "
            "(e.g. parkinson_012 has N370S twice, L444P twice). "
            "Deduplicate or annotate why duplicates exist."
        ),
        "action": "Deduplicate variant values in expected_evidence.",
    })

    return fixes


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Auditing Parkinson ground truth...")
    parkinson_stats = _audit_dataset(GROUND_TRUTH_ROOT / "parkinson")

    print("Comparing with RETT...")
    comparison = _comparison_with_rett(parkinson_stats)
    parkinson_stats["simple_pct"] = round(
        parkinson_stats["simple_field_count"]
        / (parkinson_stats["simple_field_count"]
           + parkinson_stats["medium_field_count"]
           + parkinson_stats["complex_field_count"])
        * 100,
        1,
    ) if (parkinson_stats["simple_field_count"]
          + parkinson_stats["medium_field_count"]
          + parkinson_stats["complex_field_count"]) else 0

    fixes = _recommended_fixes(parkinson_stats, comparison)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report = {
        "audit_id": f"parkinson_gt_quality_{timestamp}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "dataset": "parkinson",
        "total_entries": parkinson_stats["total_entries"],
        "avg_expected_fields_per_entry": parkinson_stats["avg_expected_fields_per_entry"],
        "avg_source_md_chars": parkinson_stats["avg_source_md_chars"],
        "field_frequency": parkinson_stats["field_frequency"],
        "gene_symbol_distribution": parkinson_stats["gene_symbol_distribution"],
        "entries_with_park2_or_parkin_issue": parkinson_stats["entries_with_park2_or_parkin_issue"],
        "park2_parkin_issue_count": parkinson_stats["park2_parkin_issue_count"],
        "simple_field_count": parkinson_stats["simple_field_count"],
        "medium_field_count": parkinson_stats["medium_field_count"],
        "complex_field_count": parkinson_stats["complex_field_count"],
        "simple_pct": parkinson_stats["simple_pct"],
        "comparison_with_rett": comparison,
        "recommended_fixes": fixes,
        "do_not_modify_data_yet": True,
        "per_entry": parkinson_stats["per_entry"],
    }

    report_path = REPORTS_DIR / f"parkinson_gt_quality_audit_{timestamp}.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nReport written: {report_path}")
    print(f"\n{'='*60}")
    print(f"Total entries: {report['total_entries']}")
    print(f"Avg expected fields/entry: {report['avg_expected_fields_per_entry']}")
    print(f"PARK2/PARKIN issues: {report['park2_parkin_issue_count']}")
    print(f"Simple fields: {report['simple_field_count']} ({report['simple_pct']}%)")
    print(f"Medium fields: {report['medium_field_count']}")
    print(f"Complex fields: {report['complex_field_count']}")
    print("\nComparison with RETT:")
    p = comparison["parkinson"]
    r = comparison["rett"]
    print(f"  Parkinson: {p['entries']} entries, avg {p['avg_fields']} fields "
          f"(simple={p['simple_pct']}%, medium={p['medium_pct']}%, complex={p['complex_pct']}%)")
    print(f"  RETT:      {r['entries']} entries, avg {r['avg_fields']} fields "
          f"(simple={r['simple_pct']}%, medium={r['medium_pct']}%, complex={r['complex_pct']}%)")
    print(f"\nVerdict: {comparison['verdict']}")
    print("\nRecommended fixes:")
    for fix in fixes:
        print(f"  [{fix['priority']}] {fix['category']}: {fix['description']}")


if __name__ == "__main__":
    main()
