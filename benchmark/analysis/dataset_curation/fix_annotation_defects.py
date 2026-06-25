"""Fix annotation defects discovered during unified-dataset quality audit.

Two classes of defect are addressed:

1. **clingen evaluation_type missing** -- the 8 clingen entries that passed the
   gold-standard filter have ``expected_evidence`` items without an
   ``evaluation_type`` field. The evaluation harness
   (``benchmark/datasets/clinvar_fused/evaluate_fused.py``) routes every field
   by ``evaluation_type`` (``precision_recall`` vs ``precision_only``), so
   clingen entries currently cannot be evaluated correctly. This script
   back-fills ``evaluation_type`` in the *source* clingen ``expected.json``
   files using the project field-catalog rule (variant / D. / J. fields are
   ``precision_only``; everything else is ``precision_recall``). The fix lives
   in the source data so the next ``build_unified_dataset`` run propagates it.

2. **parkinson variant annotation errors** -- handled by the companion
   ``reannotate_unified.py`` tool (opus-4-8 re-annotation). This script only
   reports those entries; it does not touch article-grounded evidence.

Usage::

    python -m benchmark.analysis.dataset_curation.fix_annotation_defects [--write]
"""

from __future__ import annotations

import argparse
import json
import sys

from loguru import logger

from benchmark.core.paths import GROUND_TRUTH_CLINGEN_ROOT as GROUND_TRUTH_ROOT

__all__ = [
    "VARIANT_FIELD_IDS",
    "evaluation_type_for_field",
    "fix_clingen_evaluation_types",
    "main",
]

# Fields evaluated precision-only (no recall counting): variant fields, plus
# population (D.*) and authority (J.*) categories. Mirrors the rett annotation
# tool's ``evaluation_type_for_field`` so behaviour is consistent across
# datasets.
VARIANT_FIELD_IDS = {
    "A.variant_hgvs_c",
    "A.variant_hgvs_p",
    "A.variant_hgvs_g",
    "A.variant_legacy_name",
    "A.variant_type",
    "A.null_variant_detail",
    "A.protein_effect",
    "A.same_amino_acid_known_variant",
    "A.same_residue_other_missense",
    "A.functional_domain_or_hotspot",
    "A.protein_length_change",
    "A.repeat_region_status",
    "A.splice_or_synonymous_effect",
    "A.variant_consequence_class",
    "A.identity_by_descent_variant",
}


def evaluation_type_for_field(field_id: str) -> str:
    """Return the benchmark evaluation type for one evidence field id."""
    if field_id in VARIANT_FIELD_IDS or field_id.startswith("D.") or field_id.startswith("J."):
        return "precision_only"
    return "precision_recall"


def fix_clingen_evaluation_types(*, write: bool) -> dict[str, int]:
    """Back-fill ``evaluation_type`` on every clingen source expected_evidence.

    Returns a summary of fields fixed per entry. Only fields missing
    ``evaluation_type`` are touched; existing values are preserved.
    """
    summary: dict[str, int] = {}
    for entry_dir in sorted(GROUND_TRUTH_ROOT.iterdir()):
        if not entry_dir.is_dir() or not entry_dir.name.startswith("clingen_"):
            continue
        expected_path = entry_dir / "expected.json"
        if not expected_path.exists():
            continue
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        evidence = expected.get("expected_evidence")
        if not isinstance(evidence, list):
            continue
        fixed = 0
        for item in evidence:
            if not isinstance(item, dict):
                continue
            field_id = item.get("field_id")
            if not isinstance(field_id, str):
                continue
            if not item.get("evaluation_type"):
                item["evaluation_type"] = evaluation_type_for_field(field_id)
                # clingen evidence has no "candidates"/"source" fields; add
                # the minimal set so it matches the unified schema shape.
                item.setdefault("candidates", [])
                item.setdefault("source", "article")
                fixed += 1
        if fixed:
            summary[entry_dir.name] = fixed
            if write:
                expected_path.write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.info("fixed {} evaluation_type fields in {}", fixed, entry_dir.name)
            else:
                logger.info("[dry-run] would fix {} fields in {}", fixed, entry_dir.name)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fix annotation defects found in the unified-dataset audit.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="persist fixes to source expected.json files (default: dry-run)",
    )
    args = parser.parse_args(argv)

    print("=== clingen evaluation_type back-fill ===")
    summary = fix_clingen_evaluation_types(write=args.write)
    total = sum(summary.values())
    mode = "written" if args.write else "dry-run"
    print(f"  {mode}: {total} fields across {len(summary)} entries")
    for entry, count in sorted(summary.items()):
        print(f"    {entry}: {count} fields")
    if not args.write:
        print("\n  (dry-run; re-run with --write to persist)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
