"""Shared runner for ClinGen layer-3 baseline evaluations."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import NotRequired, TypedDict

from loguru import logger

from benchmark.core import (
    GROUND_TRUTH_DIR,
    REPORTS_DIR,
    EntryMetrics,
    FieldMatch,
    compare_evidence,
    compute_aggregate_metrics,
)


class ExtractedEvidenceItem(TypedDict):
    """Minimal evidence item shape accepted by layer-3 compare_evidence."""

    field_id: str
    status: str
    value: object
    confidence: float
    source_span: NotRequired[dict[str, object]]


class FieldMatchPayload(TypedDict):
    """Serialized FieldMatch payload for report JSON."""

    field_id: str
    expected: str
    matched: bool
    extracted: str | None
    source_span: dict[str, object] | None
    match_type: str
    extra_found_values: list[str]


class EntryMetricsPayload(TypedDict):
    """Serialized EntryMetrics payload for report JSON."""

    entry_id: str
    gene_symbol: str
    disease_label: str
    classification: str
    moi: str
    language: str
    pipeline_status: str
    error_message: str | None
    duration_s: float
    evidence_count: int
    found_rate: float
    field_matches: list[FieldMatchPayload]


class BaselineReportPayload(TypedDict):
    """Serialized baseline report payload."""

    evaluation_id: str
    timestamp: str
    baseline_id: str
    baseline_name: str
    config: dict[str, object]
    total_entries: int
    total_duration_s: float
    aggregates: dict[str, object]
    per_entry: list[EntryMetricsPayload]


@dataclass(frozen=True)
class BaselineEvidenceItem:
    """Baseline extraction output for one field."""

    field_id: str
    status: str
    value: object
    confidence: float = 0.0
    source_span: dict[str, object] | None = None

    def to_extracted_item(self) -> ExtractedEvidenceItem:
        item: ExtractedEvidenceItem = {
            "field_id": self.field_id,
            "status": self.status,
            "value": self.value,
            "confidence": self.confidence,
        }
        if self.source_span is not None:
            item["source_span"] = self.source_span
        return item


@dataclass(frozen=True)
class BaselineEntry:
    """Ground-truth entry passed to baseline extractors."""

    entry_id: str
    gene_symbol: str
    disease_label: str
    classification: str = ""
    moi: str = ""
    expected_evidence: list[dict[str, object]] = field(default_factory=list)
    expected_standardization: dict[str, str] = field(default_factory=dict)
    source_path: Path | None = None


@dataclass(frozen=True)
class BaselineConfig:
    """Configuration for a baseline evaluation run."""

    baseline_id: str
    baseline_name: str
    ground_truth_dir: Path = GROUND_TRUTH_DIR
    reports_dir: Path = REPORTS_DIR
    entry_ids: tuple[str, ...] = ()
    limit: int | None = None
    save_report: bool = True
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class BaselineReport:
    """In-memory baseline report returned by the runner."""

    baseline_id: str
    baseline_name: str
    total_entries: int
    total_duration_s: float
    aggregates: dict[str, object]
    per_entry: list[EntryMetrics]
    report_path: Path | None = None


BaselineExtractor = Callable[[BaselineEntry, str], Awaitable[list[BaselineEvidenceItem]]]


def load_ground_truth_entries(config: BaselineConfig) -> list[BaselineEntry]:
    """Load ground truth entries from selection.json or manifest.json + expected.json."""
    selection_path = config.ground_truth_dir / "selection.json"
    manifest_path = config.ground_truth_dir / "manifest.json"

    if selection_path.exists():
        selection_items = json.loads(selection_path.read_text(encoding="utf-8"))
    elif manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        selection_items = [
            {"entry_id": item["unified_id"], **{k: v for k, v in item.items() if k != "unified_id"}}
            for item in manifest.get("entries", [])
        ]
    else:
        raise FileNotFoundError(
            f"Neither selection.json nor manifest.json found in {config.ground_truth_dir}"
        )

    entries: list[BaselineEntry] = []
    requested_ids = set(config.entry_ids)

    for selection_item in selection_items:
        entry_id = str(selection_item["entry_id"])
        if requested_ids and entry_id not in requested_ids:
            continue
        source_path = config.ground_truth_dir / entry_id / "source.md"
        if not source_path.exists():
            continue
        expected_path = config.ground_truth_dir / entry_id / "expected.json"
        expected_item = (
            json.loads(expected_path.read_text(encoding="utf-8"))
            if expected_path.exists()
            else {}
        )
        merged = {**selection_item, **expected_item}
        entries.append(
            BaselineEntry(
                entry_id=entry_id,
                gene_symbol=str(merged.get("gene_symbol", "")),
                disease_label=str(merged.get("disease_label", "")),
                classification=str(merged.get("classification", "")),
                moi=str(merged.get("moi", "")),
                expected_evidence=list(merged.get("expected_evidence", [])),
                expected_standardization=dict(merged.get("expected_standardization", {})),
                source_path=source_path,
            )
        )
        if config.limit is not None and len(entries) >= config.limit:
            break
    return entries


async def run_baseline_evaluation(
    config: BaselineConfig,
    extractor: BaselineExtractor,
) -> BaselineReport:
    """Run one baseline extractor against ClinGen ground truth."""
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
    if config.save_report:
        config.reports_dir.mkdir(parents=True, exist_ok=True)

    entries = load_ground_truth_entries(config)
    logger.info("Running {} on {} entries", config.baseline_id, len(entries))
    start_time = time.time()
    all_metrics: list[EntryMetrics] = []

    for entry in entries:
        entry_start = time.time()
        metrics = EntryMetrics(
            entry_id=entry.entry_id,
            gene_symbol=entry.gene_symbol,
            classification=entry.classification,
            language="en",
            moi=entry.moi,
            pipeline_status="running",
        )
        try:
            if entry.source_path is None:
                raise RuntimeError(f"missing source path for {entry.entry_id}")
            source_text = entry.source_path.read_text(encoding="utf-8")
            evidence_items = await extractor(entry, source_text)
            extracted_items = [item.to_extracted_item() for item in evidence_items]
            metrics.pipeline_status = "completed"
            metrics.evidence_count = len(extracted_items)
            found_count = sum(1 for item in extracted_items if item["status"] == "found")
            metrics.found_rate = found_count / len(extracted_items) if extracted_items else 0.0
            metrics.field_matches = compare_evidence(
                entry.expected_evidence,
                extracted_items,
                expected_standardization=entry.expected_standardization,
            )
        except Exception as exc:
            metrics.pipeline_status = "error"
            metrics.error_message = str(exc)
            metrics.field_matches = compare_evidence(
                entry.expected_evidence,
                [],
                expected_standardization=entry.expected_standardization,
            )
            logger.error("[{}] baseline failed: {}", entry.entry_id, exc)
        metrics.duration_s = round(time.time() - entry_start, 2)
        all_metrics.append(metrics)
        matched = sum(1 for match in metrics.field_matches if match.matched)
        logger.info(
            "[{}] {} | {}/{} fields | {:.0f}s",
            entry.entry_id,
            metrics.pipeline_status,
            matched,
            len(metrics.field_matches),
            metrics.duration_s,
        )

    total_duration_s = round(time.time() - start_time, 2)
    report_path: Path | None = None
    aggregates = compute_aggregate_metrics(all_metrics)
    report = BaselineReport(
        baseline_id=config.baseline_id,
        baseline_name=config.baseline_name,
        total_entries=len(entries),
        total_duration_s=total_duration_s,
        aggregates=aggregates,
        per_entry=all_metrics,
    )

    if config.save_report:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_path = config.reports_dir / f"baseline_{config.baseline_id.lower()}_{timestamp}.json"
        report_path.write_text(
            json.dumps(_serialize_report(report, config, report_path), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report = BaselineReport(
            baseline_id=report.baseline_id,
            baseline_name=report.baseline_name,
            total_entries=report.total_entries,
            total_duration_s=report.total_duration_s,
            aggregates=report.aggregates,
            per_entry=report.per_entry,
            report_path=report_path,
        )
        logger.info("Report written: {}", report_path)

    return report


def run_baseline_cli(
    baseline_id: str,
    baseline_name: str,
    extractor: BaselineExtractor,
    argv: list[str] | None = None,
) -> None:
    """CLI entrypoint shared by all baseline modules."""
    parser = argparse.ArgumentParser(description=f"Run {baseline_id}: {baseline_name}")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--entries", nargs="*", default=())
    parser.add_argument("--ground-truth-dir", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args(argv)

    report = asyncio.run(
        run_baseline_evaluation(
            BaselineConfig(
                baseline_id=baseline_id,
                baseline_name=baseline_name,
                ground_truth_dir=args.ground_truth_dir,
                reports_dir=args.reports_dir,
                entry_ids=tuple(args.entries),
                limit=args.limit,
                save_report=not args.no_save,
            ),
            extractor,
        )
    )
    overall = report.aggregates["overall"]
    print(f"{baseline_id} {baseline_name}: N={report.total_entries} overall={overall}")
    if report.report_path is not None:
        print(f"REPORT: {report.report_path}")


def _serialize_report(
    report: BaselineReport,
    config: BaselineConfig,
    report_path: Path | None,
) -> BaselineReportPayload:
    return {
        "evaluation_id": f"baseline_{report.baseline_id.lower()}_{time.strftime('%Y%m%d_%H%M%S')}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "baseline_id": report.baseline_id,
        "baseline_name": report.baseline_name,
        "config": {
            "ground_truth_dir": str(config.ground_truth_dir),
            "limit": config.limit,
            "entry_ids": list(config.entry_ids),
            "report_path": str(report_path) if report_path else None,
            **dict(config.metadata),
        },
        "total_entries": report.total_entries,
        "total_duration_s": report.total_duration_s,
        "aggregates": report.aggregates,
        "per_entry": [_serialize_entry_metrics(metric) for metric in report.per_entry],
    }


def _serialize_entry_metrics(metrics: EntryMetrics) -> EntryMetricsPayload:
    return {
        "entry_id": metrics.entry_id,
        "gene_symbol": metrics.gene_symbol,
        "disease_label": "",
        "classification": metrics.classification,
        "moi": metrics.moi,
        "language": metrics.language,
        "pipeline_status": metrics.pipeline_status,
        "error_message": metrics.error_message,
        "duration_s": metrics.duration_s,
        "evidence_count": metrics.evidence_count,
        "found_rate": metrics.found_rate,
        "field_matches": [_serialize_field_match(match) for match in metrics.field_matches],
    }


def _serialize_field_match(match: FieldMatch) -> FieldMatchPayload:
    return {
        "field_id": match.field_id,
        "expected": match.expected_value,
        "matched": match.matched,
        "extracted": match.extracted_value,
        "source_span": match.source_span,
        "match_type": match.match_type,
        "extra_found_values": match.extra_found_values,
    }
