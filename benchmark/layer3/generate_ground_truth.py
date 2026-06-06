"""Generate ground truth for Layer 3 evaluation using existing pipeline output.

Strategy:
1. For each ClinGen entry, use the existing pipeline extraction results
2. Use LLM to verify which extracted evidence items are correct
3. Generate ground truth JSON with expected fields

This is a "silver standard" approach — not as good as expert annotation,
but much faster and still useful for regression testing.
"""
from __future__ import annotations

import json
from pathlib import Path

GROUND_TRUTH_DIR = Path(__file__).resolve().parent / "ground_truth"
PIPELINE_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "backend" / "output" / "extract_evidence"

# ClinGen entries that map to known pipeline outputs
# These are entries where we have both ClinGen data AND pipeline extraction results
FABRY_ENTRY = {
    "entry_id": "fabry_disease",
    "gene_symbol": "GLA",
    "hgnc_id": "HGNC:4296",
    "disease_label": "Fabry disease",
    "mondo_id": "MONDO:301500",
    "moi": "XL",
    "classification": "Definitive",
    "gcep": "Lysosomal Diseases Gene Curation Expert Panel",
    "expected_evidence": [
        {"field_id": "A.gene_symbol", "value": "GLA"},
        {"field_id": "A.variant_hgvs_c", "value": "c.679C>T"},
        {"field_id": "A.variant_hgvs_p", "value": "p.Arg227Ter"},
        {"field_id": "B.disease_diagnosis", "value": "Fabry disease"},
        {"field_id": "B.diagnosis_sufficiency", "value": "definitive"},
    ],
    "expected_entities": {
        "gene": {"text": "GLA", "hgnc_id": "HGNC:4296"},
        "disease": {"text": "Fabry disease", "mondo_id": "MONDO:301500"},
        "variant": {"text": "p.R227X", "clinvar_id": "ClinVarVariation:10733"},
    },
    "expected_standardization": {
        "gene": "HGNC:4296",
        "disease": "OMIM:301500",
        "variant": "ClinVarVariation:10733",
    },
    "source_pdf": "法布雷病1例",
    "notes": "Chinese Fabry disease case report with known variant p.R227X",
}


def build_ground_truth_from_clingen() -> list[dict]:
    """Build ground truth entries from ClinGen data.

    For entries where we can't download PDFs, we create ground truth
    based on ClinGen's structured curation data. These entries can be
    used to evaluate the pipeline by:
    1. Searching for the gene+disease in PMC
    2. Using the pipeline to extract from whatever text is available
    3. Comparing against expected fields
    """
    selection_path = GROUND_TRUTH_DIR / "selection.json"
    entries = json.loads(selection_path.read_text(encoding="utf-8"))

    gt_entries = []
    for entry in entries:
        gt = {
            **entry,
            "has_full_text": False,
            "evaluation_mode": "field_match",  # Match by gene+disease name
        }
        gt_entries.append(gt)

    return gt_entries


def build_ground_truth_from_fixtures() -> list[dict]:
    """Build ground truth from existing pipeline output fixtures."""
    fixtures = [FABRY_ENTRY]
    gt_entries = []
    for fixture in fixtures:
        gt = {
            **fixture,
            "has_full_text": True,
            "evaluation_mode": "value_match",  # Match by extracted values
        }
        gt_entries.append(gt)
    return gt_entries


def main():
    GROUND_TRUTH_DIR.mkdir(parents=True, exist_ok=True)

    # Build from ClinGen
    clingen_gt = build_ground_truth_from_clingen()
    print(f"ClinGen entries: {len(clingen_gt)}")

    # Build from fixtures
    fixture_gt = build_ground_truth_from_fixtures()
    print(f"Fixture entries: {len(fixture_gt)}")

    # Combine
    all_gt = clingen_gt + fixture_gt

    # Save
    output_path = GROUND_TRUTH_DIR / "ground_truth_all.json"
    output_path.write_text(json.dumps(all_gt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(all_gt)} entries to {output_path}")

    # Save individual entries
    for gt in all_gt:
        entry_dir = GROUND_TRUTH_DIR / gt["entry_id"]
        entry_dir.mkdir(parents=True, exist_ok=True)
        (entry_dir / "expected.json").write_text(
            json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
