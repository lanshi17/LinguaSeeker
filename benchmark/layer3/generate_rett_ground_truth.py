"""Export Rett annotations into a Layer 3 compatible ground truth dataset."""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_ROOT = REPO_ROOT / "benchmark" / "annotation" / "ground_truth"
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "ground_truth" / "rett"
RETT_CLASSIFICATION = "Rett real-data"
RETT_GCEP = "Rett literature benchmark"


@dataclass(frozen=True)
class RettExportReport:
    """Summary of a Rett annotation export run."""

    source_root: Path
    output_root: Path
    entry_count: int


def export_rett_ground_truth(
    *,
    source_root: Path = DEFAULT_SOURCE_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> RettExportReport:
    """Copy reviewed Rett annotations into a Layer 3 ground truth root."""
    output_root.mkdir(parents=True, exist_ok=True)
    selection: list[dict[str, Any]] = []

    for source_entry_dir in sorted(source_root.glob("rett_*")):
        if not source_entry_dir.is_dir():
            continue

        expected_path = source_entry_dir / "expected.json"
        source_md_path = source_entry_dir / "source.md"
        if not expected_path.exists() or not source_md_path.exists():
            continue

        expected = _load_json(expected_path)
        meta = _load_optional_json(source_entry_dir / "meta.json")
        entry_id = str(expected.get("entry_id") or source_entry_dir.name)
        target_entry_dir = output_root / entry_id
        target_entry_dir.mkdir(parents=True, exist_ok=True)

        normalized_expected = _normalize_expected(expected, meta)
        _write_json(target_entry_dir / "expected.json", normalized_expected)
        shutil.copy2(source_md_path, target_entry_dir / "source.md")

        source_pdf_path = source_entry_dir / "source.pdf"
        if source_pdf_path.exists():
            shutil.copy2(source_pdf_path, target_entry_dir / "source.pdf")
        meta_path = source_entry_dir / "meta.json"
        if meta_path.exists():
            shutil.copy2(meta_path, target_entry_dir / "meta.json")

        selection.append(_selection_entry(normalized_expected))

    _write_json(output_root / "selection.json", selection)
    return RettExportReport(source_root=source_root, output_root=output_root, entry_count=len(selection))


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _load_json(path)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_expected(expected: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(expected)
    normalized.setdefault("source", "rett_literature")
    normalized.setdefault("gene_symbol", "MECP2")
    normalized.setdefault("hgnc_id", "HGNC:6992")
    normalized.setdefault("disease_label", "Rett syndrome")
    normalized.setdefault("mondo_id", "MONDO:0010726")
    normalized.setdefault("moi", "XD")
    normalized.setdefault("expected_evidence", [])
    normalized.setdefault("expected_entities", {})
    normalized.setdefault(
        "expected_standardization",
        {"gene": "HGNC:6992", "disease": "MONDO:0010726"},
    )
    normalized.setdefault("evaluation_config", {})
    normalized.setdefault("notes", "")
    normalized["classification"] = str(normalized.get("classification") or RETT_CLASSIFICATION)
    normalized["gcep"] = str(normalized.get("gcep") or RETT_GCEP)
    normalized["source_language"] = str(normalized.get("source_language") or meta.get("language") or "unknown")
    normalized["source_pdf_path"] = str(normalized.get("source_pdf_path") or meta.get("pdf_path") or "")
    return normalized


def _selection_entry(expected: dict[str, Any]) -> dict[str, Any]:
    return {
        "entry_id": expected.get("entry_id", ""),
        "source": expected.get("source", "rett_literature"),
        "gene_symbol": expected.get("gene_symbol", ""),
        "hgnc_id": expected.get("hgnc_id", ""),
        "disease_label": expected.get("disease_label", ""),
        "mondo_id": expected.get("mondo_id", ""),
        "moi": expected.get("moi", ""),
        "classification": expected.get("classification", RETT_CLASSIFICATION),
        "gcep": expected.get("gcep", RETT_GCEP),
        "source_pmid": expected.get("source_pmid"),
        "source_doi": expected.get("source_doi"),
        "source_title": expected.get("source_title"),
        "source_journal": expected.get("source_journal"),
        "source_year": expected.get("source_year"),
        "source_language": expected.get("source_language", ""),
        "source_pdf_path": expected.get("source_pdf_path", ""),
        "expected_evidence": expected.get("expected_evidence", []),
        "expected_entities": expected.get("expected_entities", {}),
        "expected_standardization": expected.get("expected_standardization", {}),
        "evaluation_config": expected.get("evaluation_config", {}),
        "notes": expected.get("notes", ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Rett annotations for Layer 3 evaluation")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    report = export_rett_ground_truth(source_root=args.source_root, output_root=args.output_root)
    print(f"Exported {report.entry_count} Rett entries to {report.output_root}")


if __name__ == "__main__":
    main()
