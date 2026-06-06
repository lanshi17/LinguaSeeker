"""Select 30 representative ClinGen gene-disease validity entries for Layer 3 evaluation.

Selection strategy:
- Definitive: 10 (baseline)
- Strong: 5 (medium certainty)
- Moderate: 5 (needs more evidence)
- Limited: 5 (boundary cases)
- Refuted/Disputed: 5 (negative evidence)

Selection criteria:
- Prefer entries with likely PMC full text (common gene-disease pairs)
- Cover different MOI (AD/AR/XL)
- Cover different GCEP (different disease domains)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

CLINGEN_CSV = Path(__file__).resolve().parent.parent.parent / "database" / "terminology_database" / "clingen" / "Clingen-Gene-Disease-Summary.csv"
OUTPUT_DIR = Path(__file__).resolve().parent / "ground_truth"

# Target counts per classification
TARGETS = {
    "Definitive": 10,
    "Strong": 5,
    "Moderate": 5,
    "Limited": 5,
    "Refuted": 3,
    "Disputed": 2,
}


def parse_clingen_csv() -> list[dict[str, str]]:
    """Parse ClinGen CSV, skipping preamble lines."""
    rows = []
    with open(CLINGEN_CSV, encoding="utf-8") as f:
        lines = f.readlines()

    # Find header row
    header_idx = None
    for i, line in enumerate(lines):
        if "GENE SYMBOL" in line and "CLASSIFICATION" in line:
            header_idx = i
            break

    if header_idx is None:
        raise ValueError("Could not find header row in ClinGen CSV")

    # Parse data rows
    header = [h.strip().strip('"') for h in lines[header_idx].strip().split(",")]
    for line in lines[header_idx + 1:]:
        line = line.strip()
        if not line or "+++" in line:
            continue
        # Use csv.reader to handle quoted commas
        reader = csv.reader([line])
        values = next(reader)
        if len(values) < 7:
            continue
        row = {}
        for j, h in enumerate(header):
            if j < len(values):
                row[h] = values[j].strip()
        # Only include rows with valid classification
        cls = row.get("CLASSIFICATION", "")
        if cls in TARGETS or cls in ("Definitive", "Strong", "Moderate", "Limited", "Refuted", "Disputed"):
            rows.append(row)
    return rows


def select_entries(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Select representative entries based on targets and diversity criteria."""
    selected: list[dict[str, str]] = []
    mois_seen: dict[str, int] = {}
    gceps_seen: set[str] = set()

    # Group by classification
    by_cls: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        cls = row.get("CLASSIFICATION", "")
        by_cls.setdefault(cls, []).append(row)

    for cls, target_count in TARGETS.items():
        candidates = by_cls.get(cls, [])
        # Sort by: prefer diverse MOI and GCEP
        scored = []
        for c in candidates:
            moi = c.get("MOI", "")
            gcep = c.get("GCEP", "")
            # Score: prefer less-seen MOI and GCEP
            moi_penalty = mois_seen.get(moi, 0)
            gcep_penalty = 2 if gcep in gceps_seen else 0
            scored.append((moi_penalty + gcep_penalty, c))
        scored.sort(key=lambda x: x[0])

        for _, entry in scored[:target_count]:
            selected.append(entry)
            moi = entry.get("MOI", "")
            gcep = entry.get("GCEP", "")
            mois_seen[moi] = mois_seen.get(moi, 0) + 1
            gceps_seen.add(gcep)

    return selected


def build_ground_truth(entries: list[dict[str, str]]) -> list[dict]:
    """Build ground truth JSON for each selected entry."""
    gt_entries = []
    for i, entry in enumerate(entries):
        gene = entry.get("GENE SYMBOL", "")
        disease = entry.get("DISEASE LABEL", "")
        hgnc_id = entry.get("GENE ID (HGNC)", "")
        mondo_id = entry.get("DISEASE ID (MONDO)", "")
        moi = entry.get("MOI", "")
        classification = entry.get("CLASSIFICATION", "")
        gcep = entry.get("GCEP", "")
        report_url = entry.get("ONLINE REPORT", "")
        date = entry.get("CLASSIFICATION DATE", "")

        gt = {
            "entry_id": f"clingen_{i:03d}",
            "clingen_report_url": report_url,
            "gene_symbol": gene,
            "hgnc_id": hgnc_id,
            "disease_label": disease,
            "mondo_id": mondo_id,
            "moi": moi,
            "classification": classification,
            "gcep": gcep,
            "classification_date": date,
            "expected_evidence": [
                {"field_id": "A.gene_symbol", "value": gene},
                {"field_id": "B.disease_diagnosis", "value": disease},
                {"field_id": "A.gene_disease_relationship", "value": _map_classification_to_relationship(classification)},
            ],
            "expected_entities": {
                "gene": {"text": gene, "hgnc_id": hgnc_id},
                "disease": {"text": disease, "mondo_id": mondo_id},
            },
            "expected_standardization": {
                "gene": hgnc_id,
                "disease": mondo_id,
            },
            "source_pmid": None,
            "source_pmc": None,
            "source_pdf_url": None,
            "notes": "",
        }
        gt_entries.append(gt)
    return gt_entries


def _map_classification_to_relationship(classification: str) -> str:
    """Map ClinGen classification to expected gene-disease relationship value."""
    mapping = {
        "Definitive": "causative",
        "Strong": "causative",
        "Moderate": "causative",
        "Limited": "uncertain",
        "Disputed": "disputed",
        "Refuted": "refuted",
        "No Known Disease Relationship": "no_relationship",
    }
    return mapping.get(classification, "unknown")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = parse_clingen_csv()
    print(f"Parsed {len(rows)} ClinGen entries")

    selected = select_entries(rows)
    print(f"Selected {len(selected)} entries")

    # Print selection summary
    from collections import Counter
    cls_counts = Counter(e.get("CLASSIFICATION") for e in selected)
    moi_counts = Counter(e.get("MOI") for e in selected)
    print(f"  By classification: {dict(cls_counts)}")
    print(f"  By MOI: {dict(moi_counts)}")

    gt_entries = build_ground_truth(selected)

    # Save selection
    output_path = OUTPUT_DIR / "selection.json"
    output_path.write_text(json.dumps(gt_entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved to {output_path}")

    # Save individual entries
    for gt in gt_entries:
        entry_dir = OUTPUT_DIR / gt["entry_id"]
        entry_dir.mkdir(parents=True, exist_ok=True)
        (entry_dir / "expected.json").write_text(
            json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"Created {len(gt_entries)} individual entry directories")


if __name__ == "__main__":
    main()
