"""Tests for exporting Rett annotations into Layer 3 ground truth."""
from __future__ import annotations

import json
from pathlib import Path

import asyncio

from benchmark.core import evaluate_one
from benchmark.layer3.generate_rett_ground_truth import export_rett_ground_truth


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_export_rett_ground_truth_writes_layer3_selection_and_entry(tmp_path: Path) -> None:
    """Rett annotation entries are copied into a Layer 3 compatible dataset."""
    source_root = tmp_path / "annotation" / "ground_truth"
    entry_dir = source_root / "rett_001"
    entry_dir.mkdir(parents=True)
    (entry_dir / "source.md").write_text("# Rett\x00 case\n\nMECP2 causes Rett syndrome.", encoding="utf-8")
    (entry_dir / "source.pdf").write_bytes(b"%PDF-1.4\n")
    _write_json(
        entry_dir / "meta.json",
        {
            "entry_id": "rett_001",
            "pdf_path": "/tmp/original.pdf",
            "language": "zh",
            "review_status": "ground_truth",
        },
    )
    _write_json(
        entry_dir / "expected.json",
        {
            "entry_id": "rett_001",
            "source": "rett_literature",
            "gene_symbol": "MECP2",
            "hgnc_id": "HGNC:6992",
            "disease_label": "Rett syndrome",
            "mondo_id": "MONDO:0010726",
            "moi": "XD",
            "source_title": "A Rett case",
            "source_language": "en",
            "expected_evidence": [
                {"field_id": "A.gene_symbol", "value": "MECP2"},
                {"field_id": "B.disease_diagnosis", "value": "Rett syndrome"},
            ],
            "expected_standardization": {"gene": "HGNC:6992", "disease": "MONDO:0010726"},
        },
    )

    output_root = tmp_path / "layer3" / "ground_truth" / "rett"

    report = export_rett_ground_truth(source_root=source_root, output_root=output_root)

    assert report.entry_count == 1
    assert (output_root / "rett_001" / "expected.json").exists()
    exported_source = (output_root / "rett_001" / "source.md").read_text(encoding="utf-8")
    assert "\x00" not in exported_source
    assert exported_source.startswith("# Rett case")
    assert (output_root / "rett_001" / "source.pdf").read_bytes() == b"%PDF-1.4\n"

    expected = json.loads((output_root / "rett_001" / "expected.json").read_text(encoding="utf-8"))
    assert expected["classification"] == "Rett real-data"
    assert expected["source_language"] == "en"
    assert expected["source_pdf_path"] == "/tmp/original.pdf"

    selection = json.loads((output_root / "selection.json").read_text(encoding="utf-8"))
    assert selection == [
        {
            "entry_id": "rett_001",
            "source": "rett_literature",
            "gene_symbol": "MECP2",
            "hgnc_id": "HGNC:6992",
            "disease_label": "Rett syndrome",
            "mondo_id": "MONDO:0010726",
            "moi": "XD",
            "classification": "Rett real-data",
            "gcep": "Rett literature benchmark",
            "source_pmid": None,
            "source_doi": None,
            "source_title": "A Rett case",
            "source_journal": None,
            "source_year": None,
            "source_language": "en",
            "source_pdf_path": "/tmp/original.pdf",
            "expected_evidence": [
                {"field_id": "A.gene_symbol", "value": "MECP2"},
                {"field_id": "B.disease_diagnosis", "value": "Rett syndrome"},
            ],
            "expected_entities": {},
            "expected_standardization": {"gene": "HGNC:6992", "disease": "MONDO:0010726"},
            "evaluation_config": {},
            "notes": "",
        }
    ]


def test_evaluate_one_uses_configured_ground_truth_root(tmp_path: Path) -> None:
    """The evaluator reads source.md from the caller-provided ground truth root."""
    custom_root = tmp_path / "custom_gt"
    entry_dir = custom_root / "rett_001"
    entry_dir.mkdir(parents=True)
    (entry_dir / "source.md").write_text("short", encoding="utf-8")

    metrics = asyncio.run(
        evaluate_one(
            client=None,
            base_url="http://localhost:8000",
            entry={
                "entry_id": "rett_001",
                "gene_symbol": "MECP2",
                "classification": "Rett real-data",
                "moi": "XD",
                "expected_evidence": [{"field_id": "A.gene_symbol", "value": "MECP2"}],
            },
            sf=None,
            semaphore=asyncio.Semaphore(1),
            ground_truth_dir=custom_root,
            mondo=None,
        )
    )

    assert metrics.entry_id == "rett_001"
    assert metrics.pipeline_status == "source_too_small"
    assert metrics.field_matches[0].match_type == "missing"
