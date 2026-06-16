"""Freeze raw source inventory for BIBM multilingual benchmarks."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Mapping, TypedDict

from benchmark.layer3.evaluate import REPORTS_DIR


MAIN_MULTILINGUAL_LANGUAGES = frozenset({"zh", "ja", "ko"})


class SourceInventoryRecordPayload(TypedDict):
    """Serializable source inventory record."""

    source_id: str
    source_kind: str
    source_database: str
    source_url: str | None
    article_language: str
    local_path: str
    sha256: str | None
    access_status: str
    annotation_status: str
    benchmark_layer: str
    literature_type: str | None


class SourceInventorySummaryPayload(TypedDict):
    """Serializable source inventory summary."""

    total_records: int
    structured_anchor_count: int
    clinvar_fused_entry_count: int
    raw_pdf_count: int
    main_multilingual_pdf_count: int
    by_source_database: dict[str, int]
    by_article_language: dict[str, int]
    by_annotation_status: dict[str, int]


class SourceInventoryReportPayload(TypedDict):
    """Serializable source inventory report."""

    evaluation_id: str
    timestamp: str
    config: dict[str, object]
    summary: SourceInventorySummaryPayload
    records: list[SourceInventoryRecordPayload]
    warnings: list[str]


@dataclass(frozen=True)
class SourceInventoryConfig:
    """Configuration for source inventory generation."""

    repo_root: Path = Path(__file__).resolve().parents[3]
    reports_dir: Path = REPORTS_DIR
    clinvar_root: Path | None = None
    clinvar_fused_root: Path | None = None
    pipeline_input_root: Path | None = None
    rett_download_root: Path | None = None
    download_report_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class SourceInventoryRecord:
    """One raw or structured source tracked for benchmark provenance."""

    source_id: str
    source_kind: str
    source_database: str
    source_url: str | None
    article_language: str
    local_path: str
    sha256: str | None
    access_status: str
    annotation_status: str
    benchmark_layer: str
    literature_type: str | None = None


@dataclass(frozen=True)
class SourceInventorySummary:
    """Aggregate counts for the source inventory."""

    total_records: int
    structured_anchor_count: int
    clinvar_fused_entry_count: int
    raw_pdf_count: int
    main_multilingual_pdf_count: int
    by_source_database: dict[str, int]
    by_article_language: dict[str, int]
    by_annotation_status: dict[str, int]


@dataclass(frozen=True)
class SourceInventoryReport:
    """Complete raw source inventory report."""

    config: SourceInventoryConfig
    summary: SourceInventorySummary
    records: tuple[SourceInventoryRecord, ...]
    warnings: tuple[str, ...]


def build_source_inventory_report(config: SourceInventoryConfig) -> SourceInventoryReport:
    """Build a deterministic source inventory for ClinVar and zh/ja/ko raw corpora."""
    report_index = _load_download_report_index(config.download_report_paths, config.repo_root)
    records: list[SourceInventoryRecord] = []
    warnings: list[str] = []

    records.extend(_clinvar_records(config))
    records.extend(_clinvar_fused_records(config))
    records.extend(_raw_pdf_records(config, report_index))

    records = sorted(records, key=lambda record: (record.source_kind, record.article_language, record.local_path))
    summary = SourceInventorySummary(
        total_records=len(records),
        structured_anchor_count=sum(1 for record in records if record.source_kind == "structured_anchor"),
        clinvar_fused_entry_count=sum(1 for record in records if record.source_kind == "structured_fused_entry"),
        raw_pdf_count=sum(1 for record in records if record.source_kind == "raw_pdf"),
        main_multilingual_pdf_count=sum(
            1
            for record in records
            if record.source_kind == "raw_pdf" and record.article_language in MAIN_MULTILINGUAL_LANGUAGES
        ),
        by_source_database=_count_by(records, "source_database"),
        by_article_language=_count_by(records, "article_language"),
        by_annotation_status=_count_by(records, "annotation_status"),
    )
    if summary.raw_pdf_count == 0:
        warnings.append("No raw PDF sources found under configured multilingual source roots.")
    if summary.structured_anchor_count == 0:
        warnings.append("No ClinVar structured anchor files found.")
    return SourceInventoryReport(
        config=config,
        summary=summary,
        records=tuple(records),
        warnings=tuple(warnings),
    )


def write_source_inventory_report(
    report: SourceInventoryReport,
    *,
    output_path: Path | None = None,
    reports_dir: Path | None = None,
) -> Path:
    """Persist a machine-readable source inventory report."""
    if output_path is None:
        output_dir = reports_dir or report.config.reports_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"source_inventory_{time.strftime('%Y%m%d_%H%M%S')}.json"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(source_inventory_report_to_payload(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def source_inventory_report_to_payload(report: SourceInventoryReport) -> SourceInventoryReportPayload:
    """Convert an inventory report to a JSON-serializable payload."""
    return {
        "evaluation_id": "source_inventory",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "repo_root": str(report.config.repo_root),
            "clinvar_root": str(_clinvar_root(report.config)),
            "clinvar_fused_root": str(_clinvar_fused_root(report.config)),
            "pipeline_input_root": str(_pipeline_input_root(report.config)),
            "rett_download_root": str(_rett_download_root(report.config)),
            "download_report_paths": [str(path) for path in report.config.download_report_paths],
        },
        "summary": {
            "total_records": report.summary.total_records,
            "structured_anchor_count": report.summary.structured_anchor_count,
            "clinvar_fused_entry_count": report.summary.clinvar_fused_entry_count,
            "raw_pdf_count": report.summary.raw_pdf_count,
            "main_multilingual_pdf_count": report.summary.main_multilingual_pdf_count,
            "by_source_database": dict(report.summary.by_source_database),
            "by_article_language": dict(report.summary.by_article_language),
            "by_annotation_status": dict(report.summary.by_annotation_status),
        },
        "records": [
            {
                "source_id": record.source_id,
                "source_kind": record.source_kind,
                "source_database": record.source_database,
                "source_url": record.source_url,
                "article_language": record.article_language,
                "local_path": record.local_path,
                "sha256": record.sha256,
                "access_status": record.access_status,
                "annotation_status": record.annotation_status,
                "benchmark_layer": record.benchmark_layer,
                "literature_type": record.literature_type,
            }
            for record in report.records
        ],
        "warnings": list(report.warnings),
    }


def format_source_inventory_report(report: SourceInventoryReport) -> str:
    """Format the source inventory for terminal review."""
    return (
        f"Sources={report.summary.total_records} "
        f"ClinVar={report.summary.structured_anchor_count} "
        f"ClinVarFused={report.summary.clinvar_fused_entry_count} "
        f"RawPDF={report.summary.raw_pdf_count} "
        f"MainMultilingualPDF={report.summary.main_multilingual_pdf_count}"
    )


def _clinvar_records(config: SourceInventoryConfig) -> list[SourceInventoryRecord]:
    root = _clinvar_root(config)
    files = (
        ("variant_summary.txt", "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz"),
        ("variant_summary.core.tsv", "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz"),
        ("clinvar.vcf.gz", "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz"),
    )
    records: list[SourceInventoryRecord] = []
    for filename, source_url in files:
        path = root / filename
        if not path.exists():
            continue
        records.append(
            SourceInventoryRecord(
                source_id=f"clinvar:{filename}",
                source_kind="structured_anchor",
                source_database="clinvar",
                source_url=source_url,
                article_language="en",
                local_path=_relative_to_repo(path, config.repo_root),
                sha256=_sha256_file(path),
                access_status="curated_anchor",
                annotation_status="structured_anchor",
                benchmark_layer="structured_anchor",
                literature_type=None,
            )
        )
    return records


def _clinvar_fused_records(config: SourceInventoryConfig) -> list[SourceInventoryRecord]:
    root = _clinvar_fused_root(config)
    if not root.exists():
        return []
    records: list[SourceInventoryRecord] = []
    for expected_path in sorted(root.glob("fused_*/expected.json")):
        entry_dir = expected_path.parent
        expected_payload = _load_optional_json_object(expected_path)
        source_url = _optional_str(expected_payload.get("source_pdf_url"))
        article_language = _clinvar_fused_language(entry_dir)
        records.append(
            SourceInventoryRecord(
                source_id=f"clinvar_fused:{entry_dir.name}",
                source_kind="structured_fused_entry",
                source_database="clinvar_fused",
                source_url=source_url,
                article_language=article_language,
                local_path=_relative_to_repo(entry_dir, config.repo_root),
                sha256=_sha256_file(expected_path),
                access_status="local_ground_truth",
                annotation_status="gold",
                benchmark_layer="large_structured_anchor",
                literature_type="structured_case",
            )
        )
    return records


def _raw_pdf_records(
    config: SourceInventoryConfig,
    report_index: Mapping[str, Mapping[str, Any]],
) -> list[SourceInventoryRecord]:
    records: list[SourceInventoryRecord] = []
    records.extend(
        _scan_pdf_root(
            root=_pipeline_input_root(config),
            repo_root=config.repo_root,
            benchmark_layer="multilingual_pressure_test",
            default_annotation_status="unlabeled",
            report_index=report_index,
        )
    )
    records.extend(
        _scan_pdf_root(
            root=_rett_download_root(config),
            repo_root=config.repo_root,
            benchmark_layer="rett_spot_check",
            default_annotation_status="spot_check",
            report_index=report_index,
        )
    )
    return records


def _scan_pdf_root(
    *,
    root: Path,
    repo_root: Path,
    benchmark_layer: str,
    default_annotation_status: str,
    report_index: Mapping[str, Mapping[str, Any]],
) -> list[SourceInventoryRecord]:
    if not root.exists():
        return []
    records: list[SourceInventoryRecord] = []
    for path in sorted(root.rglob("*.pdf")):
        language = _language_from_path(path, root)
        if language not in MAIN_MULTILINGUAL_LANGUAGES:
            continue
        relative_path = _relative_to_repo(path, repo_root)
        metadata = report_index.get(relative_path, {})
        source_database = _source_database_for(language, benchmark_layer, metadata)
        records.append(
            SourceInventoryRecord(
                source_id=f"{source_database}:{relative_path}",
                source_kind="raw_pdf",
                source_database=source_database,
                source_url=_optional_str(metadata.get("source_url")),
                article_language=language,
                local_path=relative_path,
                sha256=_optional_str(_metadata_sha256(metadata)) or _sha256_file(path),
                access_status="downloaded" if metadata else "local_copy",
                annotation_status=default_annotation_status,
                benchmark_layer=benchmark_layer,
                literature_type=_optional_str(metadata.get("literature_type")) or _literature_type_from_path(path, root),
            )
        )
    return records


def _load_download_report_index(
    report_paths: tuple[Path, ...],
    repo_root: Path,
) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for report_path in report_paths:
        if not report_path.exists():
            continue
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            continue
        for record in payload.get("records", []):
            if not isinstance(record, Mapping):
                continue
            file_path = _optional_str(record.get("file_path"))
            if not file_path:
                continue
            normalized = _normalize_report_path(file_path, repo_root)
            index[normalized] = record
    return index


def _metadata_sha256(metadata: Mapping[str, Any]) -> str | None:
    validation = metadata.get("_validation")
    if isinstance(validation, Mapping):
        return _optional_str(validation.get("sha256"))
    return None


def _source_database_for(
    language: str,
    benchmark_layer: str,
    metadata: Mapping[str, Any],
) -> str:
    method = _optional_str(metadata.get("method"))
    if method:
        return "openalex" if method == "openalex_oa" else method
    if benchmark_layer == "rett_spot_check":
        return "rett"
    return "local_pdf"


def _language_from_path(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return "unknown"
    if not rel.parts:
        return "unknown"
    return rel.parts[0].lower()


def _literature_type_from_path(path: Path, root: Path) -> str | None:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return None
    return rel.parts[1] if len(rel.parts) > 2 else None


def _count_by(records: list[SourceInventoryRecord], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = str(getattr(record, field_name))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _clinvar_root(config: SourceInventoryConfig) -> Path:
    return config.clinvar_root or config.repo_root / "database" / "terminology_database" / "clinvar"


def _pipeline_input_root(config: SourceInventoryConfig) -> Path:
    return config.pipeline_input_root or config.repo_root / "benchmark" / "pipeline" / "input"


def _rett_download_root(config: SourceInventoryConfig) -> Path:
    return config.rett_download_root or config.repo_root / "benchmark" / "literature_acquisition" / "downloads" / "rett"


def _clinvar_fused_root(config: SourceInventoryConfig) -> Path:
    return config.clinvar_fused_root or config.repo_root / "benchmark" / "layer3" / "clinvar_fused" / "ground_truth"


def _clinvar_fused_language(entry_dir: Path) -> str:
    languages = ["en"]
    for path in sorted(entry_dir.glob("source_*.md")):
        suffix = path.stem.removeprefix("source_")
        if suffix:
            languages.append(suffix)
    return "+".join(dict.fromkeys(languages))


def _load_optional_json_object(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, Mapping):
        return {}
    return payload


def _relative_to_repo(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _normalize_report_path(file_path: str, repo_root: Path) -> str:
    path = Path(file_path)
    if path.is_absolute():
        return _relative_to_repo(path, repo_root)
    return path.as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for source inventory generation."""
    parser = argparse.ArgumentParser(description="Build raw source inventory for BIBM multilingual benchmarks.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--clinvar-root", type=Path, default=None)
    parser.add_argument("--clinvar-fused-root", type=Path, default=None)
    parser.add_argument("--pipeline-input-root", type=Path, default=None)
    parser.add_argument("--rett-download-root", type=Path, default=None)
    parser.add_argument("--download-report", dest="download_reports", action="append", type=Path, default=[])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = build_source_inventory_report(
        SourceInventoryConfig(
            repo_root=args.repo_root,
            reports_dir=args.reports_dir,
            clinvar_root=args.clinvar_root,
            clinvar_fused_root=args.clinvar_fused_root,
            pipeline_input_root=args.pipeline_input_root,
            rett_download_root=args.rett_download_root,
            download_report_paths=tuple(args.download_reports),
        )
    )
    print(format_source_inventory_report(report))
    if args.write:
        print(f"REPORT: {write_source_inventory_report(report)}")


if __name__ == "__main__":
    main()
