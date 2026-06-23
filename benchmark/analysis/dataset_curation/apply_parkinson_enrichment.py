"""Apply enrichment plan to Parkinson ground truth expected.json files.

Applies:
  - Gene symbol corrections (PARK2→PRKN, wrong evidence gene values)
  - Variant deduplication (parkinson_012)
  - Medium fields with explicit source evidence only (inheritance, variant_type, phenotypes)

Does NOT apply:
  - uncertain inheritance assignments
  - complex fields (de_novo, segregation, functional_assay, contradiction)
  - age_of_onset (needs structured extraction)

Usage:
    python apply_parkinson_enrichment.py              # dry-run
    python apply_parkinson_enrichment.py --apply       # write changes
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
GT_DIR = ROOT / "benchmark" / "data" / "ground_truth" / "parkinson"
REPORTS_DIR = ROOT / "benchmark" / "data" / "reports"

# HGNC canonical gene symbols
# PARK2 → PRKN; others keep current; GBA stays GBA (not GBA1)
GENE_CANONICAL: dict[str, str] = {
    "PARK2": "PRKN",
    "LRRK2": "LRRK2",
    "PINK1": "PINK1",
    "GBA": "GBA",      # keep GBA per PD literature convention
    "VPS35": "VPS35",
    "GIGYF2": "GIGYF2",
}

# Gene-specific inheritance from explicit source.md text
# "explicit" = source.md has gene name + inheritance in same sentence
# "known" = well-established but no explicit text found (NOT auto-written)
GENE_INHERITANCE: dict[str, dict[str, str]] = {
    "PARK2":  {"value": "AR", "strength": "known"},
    "PINK1":  {"value": "AR", "strength": "explicit"},   # "PINK1...autosomal recessive"
    "LRRK2":  {"value": "AD", "strength": "explicit"},   # "LRRK2...autosomal dominant"
    "VPS35":  {"value": "AD", "strength": "known"},
    "GBA":    {"value": "AR", "strength": "explicit"},   # "autosomal-recessive...GBA1" (Gaucher's)
    "GIGYF2": {"value": "AD", "strength": "known"},      # suggestive but not definitive
}


def _classify_field(field_id: str) -> str:
    simple = {"A.gene_symbol", "B.disease_diagnosis", "A.gene_disease_relationship",
              "A.variant_hgvs_p", "A.variant_hgvs_c"}
    medium = {"B.mode_of_inheritance_reported", "B.hpo_terms", "B.clinical_phenotypes",
              "B.sex", "B.age_of_onset", "A.variant_type", "A.functional_domain_or_hotspot"}
    complex_ = {"C.de_novo_status", "C.segregation", "C.functional_assay",
                "C.contradictory_evidence", "C.source_grounded_evidence"}
    if field_id in simple:
        return "simple"
    if field_id in medium:
        return "medium"
    if field_id in complex_:
        return "complex"
    if field_id.startswith("A."):
        return "simple"
    if field_id.startswith("B."):
        return "medium"
    if field_id.startswith("C."):
        return "complex"
    return "unknown"


def _find_variant_types(source: str) -> list[str]:
    """Extract explicit variant types from source text."""
    patterns = {
        "missense": r"(?i)\bmissense\b",
        "nonsense": r"(?i)\bnonsense\b",
        "frameshift": r"(?i)\bframeshift\b",
        "splice_site": r"(?i)(splice[\s-]+site|splice[\s-]+variant|IVS\d)",
        "deletion": r"(?i)\b(exon[\s-]+\d+[\s-]*deletion|large[\s-]+deletion|multi[\s-]+exon)\b",
        "insertion": r"(?i)\b(6[\s-]*bp\s+insertion|insertion)\b",
        "duplication": r"(?i)\bduplication\b",
    }
    found = []
    for vtype, pat in patterns.items():
        if re.search(pat, source):
            found.append(vtype)
    return found


def _find_phenotypes(source: str) -> list[str]:
    """Extract explicit phenotype terms from source text."""
    terms = ["parkinsonism", "tremor", "rigidity", "bradykinesia",
             "dystonia", "cognitive decline", "dementia", "autonomic dysfunction"]
    return [t for t in terms if re.search(rf"(?i)\b{re.escape(t)}\b", source)]


def _deduplicate_variants(evidence: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Remove exact duplicate variant_hgvs_p values, keeping first occurrence."""
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    removed = 0
    for ev in evidence:
        if ev.get("field_id") == "A.variant_hgvs_p":
            val = str(ev.get("value", ""))
            if val in seen:
                removed += 1
                continue
            seen.add(val)
        deduped.append(ev)
    return deduped, removed


def apply_enrichment(entry_dir: Path, *, dry_run: bool = True) -> dict[str, Any]:
    """Apply enrichment to one entry. Returns change report."""
    expected_path = entry_dir / "expected.json"
    source_path = entry_dir / "source.md"
    original = json.loads(expected_path.read_text(encoding="utf-8"))
    modified = copy.deepcopy(original)
    changes: dict[str, Any] = {
        "entry_id": entry_dir.name,
        "gene_symbol_changes": [],
        "variants_deduped": 0,
        "fields_added": [],
        "fields_skipped_uncertain": [],
    }

    source_text = source_path.read_text(encoding="utf-8") if source_path.exists() else ""
    current_gene = str(original.get("gene_symbol", ""))
    canonical_gene = GENE_CANONICAL.get(current_gene, current_gene)

    # ── 1. Gene symbol fixes ──
    if current_gene != canonical_gene:
        modified["gene_symbol"] = canonical_gene
        changes["gene_symbol_changes"].append({
            "field": "gene_symbol",
            "from": current_gene,
            "to": canonical_gene,
        })

    # Fix expected_standardization.gene if present
    std_gene = modified.get("expected_standardization", {}).get("gene", "")
    if std_gene == "PARK2":
        modified.setdefault("expected_standardization", {})["gene"] = "PRKN"
        changes["gene_symbol_changes"].append({
            "field": "expected_standardization.gene",
            "from": "PARK2",
            "to": "PRKN",
        })

    # Fix expected_entities.gene.text if present
    ent_gene = modified.get("expected_entities", {}).get("gene", {}).get("text", "")
    if ent_gene == "PARK2":
        modified["expected_entities"]["gene"]["text"] = "PRKN"
        changes["gene_symbol_changes"].append({
            "field": "expected_entities.gene.text",
            "from": "PARK2",
            "to": "PRKN",
        })

    # Fix A.gene_symbol evidence value
    evidence = modified.get("expected_evidence", [])
    for ev in evidence:
        if ev.get("field_id") == "A.gene_symbol":
            old_val = str(ev.get("value", ""))
            new_val = canonical_gene
            if old_val != new_val:
                ev["value"] = new_val
                changes["gene_symbol_changes"].append({
                    "field": "expected_evidence A.gene_symbol",
                    "from": old_val,
                    "to": new_val,
                })

    # ── 2. Variant deduplication ──
    evidence, deduped_count = _deduplicate_variants(evidence)
    changes["variants_deduped"] = deduped_count

    # ── 3. Medium fields ──
    existing_fields = {ev.get("field_id") for ev in evidence}

    # 3a. Inheritance
    if "B.mode_of_inheritance_reported" not in existing_fields:
        inh_info = GENE_INHERITANCE.get(canonical_gene, {})
        inh_value = inh_info.get("value", "")
        inh_strength = inh_info.get("strength", "")
        if inh_strength == "explicit" and inh_value:
            evidence.append({
                "field_id": "B.mode_of_inheritance_reported",
                "value": inh_value,
                "candidates": [],
                "source": "article",
                "evaluation_type": "precision_recall",
            })
            changes["fields_added"].append({
                "field_id": "B.mode_of_inheritance_reported",
                "value": inh_value,
                "evidence_strength": "explicit",
            })
        elif inh_strength == "known" and inh_value:
            changes["fields_skipped_uncertain"].append({
                "field_id": "B.mode_of_inheritance_reported",
                "value": inh_value,
                "reason": f"No explicit gene-specific inheritance text for {canonical_gene} in source.md",
            })

    # 3b. Variant types
    if "A.variant_type" not in existing_fields:
        vtypes = _find_variant_types(source_text)
        if vtypes:
            evidence.append({
                "field_id": "A.variant_type",
                "value": ", ".join(vtypes),
                "candidates": [],
                "source": "article",
                "evaluation_type": "precision_recall",
            })
            changes["fields_added"].append({
                "field_id": "A.variant_type",
                "value": ", ".join(vtypes),
                "evidence_strength": "explicit",
            })

    # 3c. Clinical phenotypes
    if "B.clinical_phenotypes" not in existing_fields:
        phenos = _find_phenotypes(source_text)
        if phenos:
            evidence.append({
                "field_id": "B.clinical_phenotypes",
                "value": "; ".join(phenos),
                "candidates": [],
                "source": "article",
                "evaluation_type": "precision_recall",
            })
            changes["fields_added"].append({
                "field_id": "B.clinical_phenotypes",
                "value": "; ".join(phenos),
                "evidence_strength": "explicit",
            })

    modified["expected_evidence"] = evidence

    # ── Write or report ──
    if not dry_run:
        expected_path.write_text(
            json.dumps(modified, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    changes["fields_before"] = len(original.get("expected_evidence", []))
    changes["fields_after"] = len(evidence)
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Parkinson GT enrichment")
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    args = parser.parse_args()
    dry_run = not args.apply

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    all_changes: list[dict[str, Any]] = []
    fields_before_total = 0
    fields_after_total = 0
    gene_errors_before = 0
    gene_errors_after = 0

    for entry_dir in sorted(GT_DIR.iterdir()):
        if not entry_dir.is_dir():
            continue
        expected_path = entry_dir / "expected.json"
        if not expected_path.exists():
            continue

        original = json.loads(expected_path.read_text(encoding="utf-8"))
        fields_before = len(original.get("expected_evidence", []))
        fields_before_total += fields_before

        # Count gene errors before
        gene = str(original.get("gene_symbol", ""))
        canonical = GENE_CANONICAL.get(gene, gene)
        for ev in original.get("expected_evidence", []):
            if ev.get("field_id") == "A.gene_symbol" and str(ev.get("value", "")) != canonical:
                gene_errors_before += 1

        changes = apply_enrichment(entry_dir, dry_run=dry_run)
        fields_after = changes.get("fields_after", fields_before)
        fields_after_total += fields_after

        # Count gene errors after
        modified = json.loads(expected_path.read_text(encoding="utf-8")) if not dry_run else original
        if not dry_run:
            mod_gene = str(modified.get("gene_symbol", ""))
            mod_canonical = GENE_CANONICAL.get(mod_gene, mod_gene)
            for ev in modified.get("expected_evidence", []):
                if ev.get("field_id") == "A.gene_symbol" and str(ev.get("value", "")) != mod_canonical:
                    gene_errors_after += 1

        all_changes.append(changes)
        n_added = len(changes["fields_added"])
        n_skipped = len(changes["fields_skipped_uncertain"])
        n_dedup = changes["variants_deduped"]
        gene_changes = len(changes["gene_symbol_changes"])
        print(f"{entry_dir.name}: +{n_added} fields, {n_skipped} skipped, "
              f"{n_dedup} deduped, {gene_changes} gene fixes "
              f"({fields_before}→{fields_after})")

    # Statistics — compute from changes to work correctly in dry-run mode
    simple_after = 0
    medium_after = 0
    complex_after = 0
    for changes in all_changes:
        # All original fields are simple; count added fields by category
        simple_after += changes.get("fields_before", 0)
        for added in changes.get("fields_added", []):
            cat = _classify_field(added["field_id"])
            if cat == "simple":
                simple_after += 1
            elif cat == "medium":
                medium_after += 1
            elif cat == "complex":
                complex_after += 1

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report = {
        "application_id": f"parkinson_gt_enrichment_applied_{timestamp}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "dry_run": dry_run,
        "modified_entries": len(all_changes),
        "gene_symbol_errors_before": gene_errors_before,
        "gene_symbol_errors_after": gene_errors_after,
        "total_gene_symbol_changes": sum(len(c["gene_symbol_changes"]) for c in all_changes),
        "duplicate_variants_removed": sum(c["variants_deduped"] for c in all_changes),
        "fields_before_total": fields_before_total,
        "fields_after_total": fields_after_total,
        "avg_fields_before": round(fields_before_total / 20, 2),
        "avg_fields_after": round(fields_after_total / 20, 2),
        "simple_count_after": simple_after,
        "medium_count_after": medium_after,
        "complex_count_after": complex_after,
        "total_fields_added": sum(len(c["fields_added"]) for c in all_changes),
        "total_skipped_uncertain": sum(len(c["fields_skipped_uncertain"]) for c in all_changes),
        "per_entry": all_changes,
    }

    report_path = REPORTS_DIR / f"parkinson_gt_enrichment_applied_{timestamp}.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n{'DRY RUN' if dry_run else 'APPLIED'}: {report_path}")
    print(f"Gene errors: {gene_errors_before}→{gene_errors_after}")
    print(f"Fields: {fields_before_total}→{fields_after_total} (avg {report['avg_fields_before']}→{report['avg_fields_after']})")
    print(f"Added: {report['total_fields_added']}, Skipped uncertain: {report['total_skipped_uncertain']}")
    print(f"Deduped variants: {report['duplicate_variants_removed']}")
    print(f"After: simple={simple_after} medium={medium_after} complex={complex_after}")


if __name__ == "__main__":
    main()
