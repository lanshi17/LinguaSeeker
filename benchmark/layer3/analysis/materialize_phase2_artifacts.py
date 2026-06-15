"""Materialize runtime Phase 2 artifacts into Layer 3 benchmark preprocessed paths."""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

from benchmark.layer3.analysis.inventory_system_runs import (
    build_inventory,
    is_reconstructable_run,
    load_postgres_env_from_vault,
    query_system_run_rows,
)
from benchmark.layer3.evaluate import GROUND_TRUTH_DIR
from src.dao.postgresql.connection import async_session_factory, build_async_engine
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceExtractionResult,
    ExtractionTarget,
    Track,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PIPELINE_ROOT = REPO_ROOT / "backend" / "data" / "pipeline"


@dataclass(frozen=True)
class MaterializeConfig:
    """Configuration for Phase 2 artifact materialization."""

    pipeline_root: Path = DEFAULT_PIPELINE_ROOT
    ground_truth_dir: Path = GROUND_TRUTH_DIR
    entry_ids: tuple[str, ...] = ()
    write: bool = False
    overwrite: bool = False


@dataclass(frozen=True)
class MaterializeRow:
    """Materialization decision for one benchmark entry."""

    entry_id: str
    status: str
    source_path: Path | None = None
    destination_path: Path | None = None
    message: str = ""


@dataclass(frozen=True)
class MaterializeReport:
    """Summary of Phase 2 artifact materialization."""

    rows: tuple[MaterializeRow, ...]

    @property
    def materialized_count(self) -> int:
        """Count entries written in this run."""
        return sum(1 for row in self.rows if row.status == "materialized")

    @property
    def would_materialize_count(self) -> int:
        """Count entries that would be written in dry-run mode."""
        return sum(1 for row in self.rows if row.status == "would_materialize")


@dataclass(frozen=True)
class DbEvidenceRow:
    """Run-evidence row data needed to reconstruct one EvidenceItem."""

    track: str
    raw_payload: dict[str, object]


def build_dual_result_from_db_rows(
    *,
    entry_id: str,
    gene_symbol: str,
    disease_name: str,
    processing_run_id: str,
    source_document_id: str,
    rows: tuple[DbEvidenceRow, ...],
) -> DualEvidenceExtractionResult:
    """Reconstruct a minimal dual extraction result from persisted run-evidence raw payloads."""
    target = ExtractionTarget(
        gene_symbol=gene_symbol,
        disease_name=disease_name,
        clingen_entry_id=entry_id,
    )
    original_items = _items_for_track(rows, Track.ORIGINAL)
    translated_items = _items_for_track(rows, Track.TRANSLATED)
    return DualEvidenceExtractionResult(
        document_id=source_document_id,
        original_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id=source_document_id,
            track=Track.ORIGINAL,
            evidence_items=original_items,
            extraction_target=target,
        ),
        translated_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id=source_document_id,
            track=Track.TRANSLATED,
            evidence_items=translated_items,
            extraction_target=target,
        ),
    )


def materialize_phase2_artifacts(config: MaterializeConfig) -> MaterializeReport:
    """Copy matching runtime Phase 2 extraction results to benchmark preprocessed paths."""
    expected_entries = _selected_entry_ids(config)
    artifacts = _scan_artifacts(config.pipeline_root)
    rows: list[MaterializeRow] = []
    for entry_id in expected_entries:
        source_path = artifacts.get(entry_id)
        destination_path = _destination_path(config.ground_truth_dir, entry_id)
        if source_path is None:
            rows.append(
                MaterializeRow(
                    entry_id=entry_id,
                    status="missing_artifact",
                    destination_path=destination_path,
                    message="No matching runtime Phase 2 extraction_result.json found.",
                )
            )
            continue
        if destination_path.exists() and destination_path.read_bytes() == source_path.read_bytes():
            rows.append(
                MaterializeRow(
                    entry_id=entry_id,
                    status="already_materialized",
                    source_path=source_path,
                    destination_path=destination_path,
                )
            )
            continue
        if config.write:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)
            status = "materialized"
        else:
            status = "would_materialize"
        rows.append(
            MaterializeRow(
                entry_id=entry_id,
                status=status,
                source_path=source_path,
                destination_path=destination_path,
            )
        )
    return MaterializeReport(rows=tuple(rows))


def materialize_reconstructed_artifacts(
    config: MaterializeConfig,
    reconstructed_results: dict[str, DualEvidenceExtractionResult],
) -> MaterializeReport:
    """Write reconstructed dual extraction results to benchmark preprocessed paths."""
    rows: list[MaterializeRow] = []
    for entry_id in _selected_entry_ids(config):
        result = reconstructed_results.get(entry_id)
        destination_path = _destination_path(config.ground_truth_dir, entry_id)
        if result is None:
            rows.append(
                MaterializeRow(
                    entry_id=entry_id,
                    status="missing_db_reconstruction",
                    destination_path=destination_path,
                    message="No reconstructed DB artifact available.",
                )
            )
            continue
        payload = result.model_dump_json()
        if destination_path.exists():
            if destination_path.read_text(encoding="utf-8") == payload:
                status = "already_materialized"
            elif not config.overwrite:
                status = "existing_artifact_differs"
            elif config.write:
                destination_path.write_text(payload, encoding="utf-8")
                status = "materialized"
            else:
                status = "would_materialize"
        elif config.write:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            destination_path.write_text(payload, encoding="utf-8")
            status = "materialized"
        else:
            status = "would_materialize"
        rows.append(
            MaterializeRow(
                entry_id=entry_id,
                status=status,
                destination_path=destination_path,
                message="reconstructed_from_db",
            )
        )
    return MaterializeReport(rows=tuple(rows))


async def materialize_phase2_artifacts_from_db(
    config: MaterializeConfig,
    vault_path: Path | None = None,
) -> MaterializeReport:
    """Reconstruct benchmark Phase 2 artifacts from persisted run_evidence_items rows."""
    load_postgres_env_from_vault(vault_path)
    selected_entry_ids = _selected_entry_ids(config)
    inventory = build_inventory(await query_system_run_rows(), selected_entry_ids)
    reconstructed: dict[str, DualEvidenceExtractionResult] = {}
    for entry_id, run in inventory.best_by_entry.items():
        if not is_reconstructable_run(run):
            continue
        metadata = _entry_metadata(config.ground_truth_dir, entry_id)
        rows = await _query_db_evidence_rows(run.processing_run_id)
        reconstructed[entry_id] = build_dual_result_from_db_rows(
            entry_id=entry_id,
            gene_symbol=metadata["gene_symbol"],
            disease_name=metadata["disease_name"],
            processing_run_id=run.processing_run_id,
            source_document_id=run.source_document_id,
            rows=rows,
        )
    return materialize_reconstructed_artifacts(config, reconstructed)


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-root", type=Path, default=DEFAULT_PIPELINE_ROOT)
    parser.add_argument("--ground-truth-dir", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--entries", nargs="*", default=())
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing existing differing artifacts.")
    parser.add_argument("--from-db", action="store_true", help="Reconstruct artifacts from run_evidence_items.")
    parser.add_argument(
        "--backfill-language",
        action="store_true",
        help=(
            "Stamp article_language metadata onto evidence items in existing "
            "phase_2 artifacts (idempotent; respects --write)."
        ),
    )
    parser.add_argument("--vault", type=Path, default=None, help="Optional backend vault path for DB credentials.")
    args = parser.parse_args(argv)

    config = MaterializeConfig(
        pipeline_root=args.pipeline_root,
        ground_truth_dir=args.ground_truth_dir,
        entry_ids=tuple(args.entries),
        write=args.write,
        overwrite=args.overwrite,
    )
    if args.backfill_language:
        report = backfill_language_metadata(config)
        print(format_backfill_report(report))
        return
    if args.from_db:
        report = asyncio.run(
            materialize_phase2_artifacts_from_db(
                config,
                vault_path=args.vault,
            )
        )
    else:
        report = materialize_phase2_artifacts(config)
    print(format_materialize_report(report))


def backfill_language_metadata(config: MaterializeConfig) -> MaterializeReport:
    """Stamp article_language onto evidence items of existing phase_2 artifacts.

    The Layer 3 ClinGen N=30 corpus is English-only: both the original track
    and the translated track are English. This helper makes existing
    pre-language-metadata artifacts consistent with the workflow fix, so the
    benchmark metrics read valid ``article_language`` / ``is_english`` /
    ``requires_translation`` / ``evidence_source_language`` without re-running
    the full pipeline. Idempotent: items already carrying language metadata
    are left untouched.
    """
    rows: list[MaterializeRow] = []
    for entry_id in _selected_entry_ids(config):
        artifact_path = _destination_path(config.ground_truth_dir, entry_id)
        if not artifact_path.exists():
            rows.append(
                MaterializeRow(
                    entry_id=entry_id,
                    status="missing_artifact",
                    destination_path=artifact_path,
                    message="No phase_2 extraction_result.json to backfill.",
                )
            )
            continue
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        stamped, changed = _stamp_artifact_language(payload, config, entry_id)
        if not changed:
            rows.append(
                MaterializeRow(
                    entry_id=entry_id,
                    status="already_materialized",
                    destination_path=artifact_path,
                    message="All items already carry language metadata.",
                )
            )
            continue
        if config.write:
            artifact_path.write_text(
                json.dumps(stamped, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            status = "materialized"
        else:
            status = "would_materialize"
        rows.append(
            MaterializeRow(
                entry_id=entry_id,
                status=status,
                destination_path=artifact_path,
                message="backfilled_language_metadata",
            )
        )
    return MaterializeReport(rows=tuple(rows))


def _stamp_artifact_language(
    payload: dict[str, object],
    config: MaterializeConfig,
    entry_id: str,
) -> tuple[dict[str, object], bool]:
    """Return ``(payload, changed)`` with language metadata stamped on evidence items."""
    metadata = _entry_metadata(config.ground_truth_dir, entry_id)
    target_gene = metadata.get("gene_symbol", "")
    target_disease = metadata.get("disease_name", "")
    changed = False
    for track_key, default_language in (
        ("original_result", "en"),
        ("translated_result", "en"),
    ):
        track_result = payload.get(track_key)
        if not isinstance(track_result, dict):
            continue
        items = track_result.get("evidence_items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            existing = item.get("article_language")
            if isinstance(existing, str) and existing.strip():
                continue
            is_english = default_language in {"en", "eng", "english"}
            item["article_language"] = default_language
            item["is_english"] = is_english
            item["requires_translation"] = not is_english
            item["evidence_source_language"] = default_language
            if not item.get("target_gene") and target_gene:
                item["target_gene"] = target_gene
            if not item.get("target_disease") and target_disease:
                item["target_disease"] = target_disease
            changed = True
    return payload, changed


def format_backfill_report(report: MaterializeReport) -> str:
    """Format the language-metadata backfill report for terminal output."""
    lines = [
        (
            f"backfilled={report.materialized_count} "
            f"would_backfill={report.would_materialize_count} total={len(report.rows)}"
        ),
        "entry status destination message",
    ]
    for row in report.rows:
        destination = str(row.destination_path) if row.destination_path is not None else "-"
        lines.append(f"{row.entry_id} {row.status} {destination} {row.message}")
    return "\n".join(lines)


def format_materialize_report(report: MaterializeReport) -> str:
    """Format materialization report for terminal output."""
    lines = [
        (
            f"materialized={report.materialized_count} "
            f"would_materialize={report.would_materialize_count} total={len(report.rows)}"
        ),
        "entry status source destination",
    ]
    for row in report.rows:
        source = str(row.source_path) if row.source_path is not None else "-"
        destination = str(row.destination_path) if row.destination_path is not None else "-"
        lines.append(f"{row.entry_id} {row.status} {source} {destination}")
    return "\n".join(lines)


def _selected_entry_ids(config: MaterializeConfig) -> list[str]:
    if config.entry_ids:
        return list(config.entry_ids)
    selection_path = config.ground_truth_dir / "selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    return [str(item["entry_id"]) for item in selection]


def _entry_metadata(ground_truth_dir: Path, entry_id: str) -> dict[str, str]:
    expected_path = ground_truth_dir / entry_id / "expected.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8")) if expected_path.exists() else {}
    if expected:
        return {
            "gene_symbol": str(expected.get("gene_symbol", "")),
            "disease_name": str(expected.get("disease_label", "")),
        }
    selection_path = ground_truth_dir / "selection.json"
    for item in json.loads(selection_path.read_text(encoding="utf-8")):
        if str(item.get("entry_id")) == entry_id:
            return {
                "gene_symbol": str(item.get("gene_symbol", "")),
                "disease_name": str(item.get("disease_label", "")),
            }
    raise ValueError(f"entry metadata not found for {entry_id}")


async def _query_db_evidence_rows(processing_run_id: str) -> tuple[DbEvidenceRow, ...]:
    engine = build_async_engine()
    session_factory = async_session_factory(engine)
    try:
        async with session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        """
                        select track, raw_payload
                        from run_evidence_items
                        where processing_run_id = cast(:processing_run_id as uuid)
                        order by track, field_id, run_evidence_item_id
                        """
                    ),
                    {"processing_run_id": processing_run_id},
                )
            ).mappings().all()
    finally:
        await engine.dispose()
    return tuple(
        DbEvidenceRow(track=str(row["track"]), raw_payload=dict(row["raw_payload"] or {}))
        for row in rows
        if isinstance(row["raw_payload"], dict)
    )


def _scan_artifacts(pipeline_root: Path) -> dict[str, Path]:
    artifacts: dict[str, Path] = {}
    for artifact_path in sorted(pipeline_root.glob("*/phase_2/extraction_result.json")):
        result = _load_result(artifact_path)
        entry_id = _extract_entry_id(result)
        if not entry_id:
            continue
        artifacts[entry_id] = artifact_path
    return artifacts


def _load_result(path: Path) -> DualEvidenceExtractionResult:
    return DualEvidenceExtractionResult.model_validate_json(path.read_text(encoding="utf-8"))


def _extract_entry_id(result: DualEvidenceExtractionResult) -> str:
    for track_result in (
        result.reconciled_result,
        result.original_result,
        result.translated_result,
    ):
        if track_result is None:
            continue
        entry_id = _target_entry_id(track_result)
        if entry_id:
            return entry_id
    return ""


def _target_entry_id(result: EvidenceExtractionResult) -> str:
    if result.extraction_target is None:
        return ""
    return result.extraction_target.clingen_entry_id


def _items_for_track(rows: tuple[DbEvidenceRow, ...], track: Track) -> list[EvidenceItem]:
    return [
        EvidenceItem.model_validate(row.raw_payload)
        for row in rows
        if row.track == track.value
    ]


def _destination_path(ground_truth_dir: Path, entry_id: str) -> Path:
    return ground_truth_dir / entry_id / "preprocessed" / "phase_2" / "extraction_result.json"


if __name__ == "__main__":
    main()
