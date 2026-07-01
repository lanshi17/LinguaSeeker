"""Tests for raw source inventory generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from benchmark.analysis.dataset_curation.source_inventory import (
    SourceInventoryConfig,
    build_source_inventory_report,
    write_source_inventory_report,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_pdf(path: Path, content: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return _sha256(content)


def _write_text(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return _sha256(content.encode("utf-8"))


def test_build_source_inventory_merges_report_metadata_and_classifies_layers(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path

    clinvar_root = repo_root / "database" / "terminology_database" / "clinvar"
    clinvar_summary_sha = _write_text(clinvar_root / "variant_summary.txt", "clinvar-summary\n")
    _write_text(clinvar_root / "variant_summary.core.tsv", "clinvar-core\n")
    _write_pdf(clinvar_root / "clinvar.vcf.gz", b"clinvar-vcf\n")
    fused_root = repo_root / "benchmark" / "layer3" / "clinvar_fused" / "ground_truth"
    fused_expected_sha = _write_text(
        fused_root / "fused_000" / "expected.json",
        json.dumps(
            {
                "entry_id": "fused_000",
                "source_pdf_url": "https://example.org/fused.pdf",
            }
        ),
    )
    _write_text(fused_root / "fused_000" / "source.md", "English source\n")
    _write_text(fused_root / "fused_000" / "source_zh.md", "中文来源\n")
    _write_text(fused_root / "selection.json", json.dumps(["fused_000"]))

    zh_pdf = repo_root / "benchmark" / "pipeline" / "input" / "zh" / "paper_a.pdf"
    zh_sha = _write_pdf(zh_pdf, b"%PDF-1.4\nzh-paper\n")
    ko_pdf = repo_root / "benchmark" / "pipeline" / "input" / "ko" / "paper_c.pdf"
    ko_sha = _write_pdf(ko_pdf, b"%PDF-1.4\nko-paper\n")
    ja_pdf = repo_root / "benchmark" / "literature_acquisition" / "downloads" / "rett" / "ja" / "paper_b.pdf"
    ja_sha = _write_pdf(ja_pdf, b"%PDF-1.4\nja-paper\n")

    report_path = repo_root / "download_report.json"
    report_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "file_path": str(zh_pdf.relative_to(repo_root)),
                        "source_url": "https://example.org/zh-paper",
                        "lang": "zh",
                        "method": "openalex_oa",
                        "literature_type": "case_report",
                        "_validation": {"sha256": zh_sha},
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    report = build_source_inventory_report(
        SourceInventoryConfig(
            repo_root=repo_root,
            download_report_paths=(report_path,),
        )
    )

    assert report.summary.total_records == 7
    assert report.summary.structured_anchor_count == 3
    assert report.summary.clinvar_fused_entry_count == 1
    assert report.summary.raw_pdf_count == 3
    assert report.summary.by_source_database["clinvar"] == 3
    assert report.summary.by_source_database["clinvar_fused"] == 1
    assert report.summary.by_source_database["local_pdf"] == 1
    assert report.summary.by_source_database["openalex"] == 1
    assert report.summary.by_source_database["rett"] == 1
    assert report.summary.by_article_language["en"] == 3
    assert report.summary.by_article_language["zh"] == 1
    assert report.summary.by_article_language["ja"] == 1

    by_name = {Path(record.local_path).name: record for record in report.records}

    clinvar_record = by_name["variant_summary.txt"]
    assert clinvar_record.source_database == "clinvar"
    assert clinvar_record.source_kind == "structured_anchor"
    assert clinvar_record.article_language == "en"
    assert clinvar_record.source_url.endswith("variant_summary.txt.gz")
    assert clinvar_record.sha256 == clinvar_summary_sha
    assert clinvar_record.access_status == "curated_anchor"
    assert clinvar_record.annotation_status == "structured_anchor"

    fused_record = by_name["fused_000"]
    assert fused_record.source_database == "clinvar_fused"
    assert fused_record.source_kind == "structured_fused_entry"
    assert fused_record.article_language == "en+zh"
    assert fused_record.source_url == "https://example.org/fused.pdf"
    assert fused_record.sha256 == fused_expected_sha
    assert fused_record.access_status == "local_ground_truth"
    assert fused_record.annotation_status == "gold"

    zh_record = by_name["paper_a.pdf"]
    assert zh_record.source_database == "openalex"
    assert zh_record.article_language == "zh"
    assert zh_record.source_url == "https://example.org/zh-paper"
    assert zh_record.sha256 == zh_sha
    assert zh_record.access_status == "downloaded"
    assert zh_record.annotation_status == "unlabeled"

    ko_record = by_name["paper_c.pdf"]
    assert ko_record.source_database == "local_pdf"
    assert ko_record.article_language == "ko"
    assert ko_record.source_url is None
    assert ko_record.sha256 == ko_sha
    assert ko_record.access_status == "local_copy"
    assert ko_record.annotation_status == "unlabeled"

    ja_record = by_name["paper_b.pdf"]
    assert ja_record.source_database == "rett"
    assert ja_record.article_language == "ja"
    assert ja_record.source_url is None
    assert ja_record.sha256 == ja_sha
    assert ja_record.access_status == "local_copy"
    assert ja_record.annotation_status == "spot_check"


def test_write_source_inventory_report_persists_json(tmp_path: Path) -> None:
    repo_root = tmp_path
    clinvar_root = repo_root / "database" / "terminology_database" / "clinvar"
    _write_text(clinvar_root / "variant_summary.txt", "clinvar-summary\n")
    _write_text(clinvar_root / "variant_summary.core.tsv", "clinvar-core\n")
    _write_pdf(clinvar_root / "clinvar.vcf.gz", b"clinvar-vcf\n")

    report = build_source_inventory_report(SourceInventoryConfig(repo_root=repo_root))
    output_path = repo_root / "reports" / "source_inventory.json"
    written_path = write_source_inventory_report(report, output_path=output_path)

    payload = json.loads(written_path.read_text(encoding="utf-8"))
    assert written_path == output_path
    assert payload["summary"]["total_records"] == 3
    assert payload["records"][0]["source_database"] == "clinvar"
