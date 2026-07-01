"""Run Phase 3 entity standardization E2E over extract_evidence outputs.

Usage:
    cd backend

    uv run python scripts/e2e_standardize_entities.py
    uv run python scripts/e2e_standardize_entities.py --refresh-upstream
    uv run python scripts/e2e_standardize_entities.py --import-terminology
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.e2e_extract_evidence import run_extract_evidence
from src.core.config import Settings, get_config
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
)
from src.core.standardize_entities_and_align_knowledge.api import (
    EntityStandardizationService,
    build_summary_metadata,
    import_terminology,
    serialize_matches,
)
from src.core.standardize_entities_and_align_knowledge.contracts import StandardizationResult
from src.dao.postgresql.connection import async_session_factory, build_async_engine, get_async_session


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CROSS_LINGUAL_INPUT_DIR = BACKEND_DIR / "output" / "cross_lingual" / "zh" / "法布雷病1例"
DEFAULT_EXTRACT_EVIDENCE_DIR = BACKEND_DIR / "output" / "extract_evidence" / "法布雷病1例" / "latest"
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "output" / "standardize_entities"
DEFAULT_TERMINOLOGY_ROOT = BACKEND_DIR.parent / "database" / "terminology_database"
DEFAULT_TERMINOLOGY_SOURCES = ("hgnc", "omim", "hpo", "clingen", "clinvar")


def _configure_logger() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")


def _json_ready(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    return value


def _write_json(path: Path, data: BaseModel | dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_ready(data), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _read_dual_result(path: Path) -> DualEvidenceExtractionResult:
    data = json.loads(path.read_text(encoding="utf-8"))
    return DualEvidenceExtractionResult.model_validate(data)


def _open_standardization_session(cfg: Settings):
    engine = build_async_engine(cfg)
    return engine, async_session_factory(engine)


async def _refresh_upstream_if_requested(
    *,
    refresh_upstream: bool,
    cross_lingual_input_dir: Path,
    extract_output_dir: Path,
    refresh_run_id: str,
) -> Path | None:
    if not refresh_upstream:
        return None
    logger.info(
        "Refreshing extract_evidence upstream from {} into {}",
        cross_lingual_input_dir,
        extract_output_dir,
    )
    return await run_extract_evidence(
        input_dir=cross_lingual_input_dir,
        output_dir=extract_output_dir,
        run_id=refresh_run_id,
    )


async def _import_terminology_if_requested(
    *,
    cfg: Settings,
    terminology_root: Path,
    version: str,
    sources: list[str],
) -> None:
    logger.info("Importing terminology: root={}, version={}, sources={}", terminology_root, version, sources)
    await import_terminology(
        cfg=cfg,
        terminology_root=terminology_root,
        version=version,
        sources=sources,
    )


def _summary(
    *,
    standardization_result: StandardizationResult,
    dual_result: DualEvidenceExtractionResult,
    extract_evidence_dir: Path,
    saved_dir: Path,
    source_document_id: str,
    processing_run_id: str,
    refreshed_upstream: bool,
    imported_terminology: bool,
    terminology_root: Path,
    terminology_version: str,
    terminology_sources: list[str],
    terminology_entry_count: int = 0,
    embedding_available: bool = False,
) -> dict[str, Any]:
    summary = {
        "document_id": standardization_result.document_id,
        "extract_evidence_dir": str(extract_evidence_dir),
        "output_dir": str(saved_dir),
        "created_at": datetime.now().isoformat(),
        "source_document_id": source_document_id,
        "processing_run_id": processing_run_id,
        "match_count": standardization_result.match_count,
        "standardized_count": standardization_result.standardized_count,
        "ambiguous_count": standardization_result.ambiguous_count,
        "unmapped_count": standardization_result.unmapped_count,
        "normalized_entity_count": len(standardization_result.normalized_entity_ids),
        "normalized_entity_ids": list(standardization_result.normalized_entity_ids),
        "original_chain_count": len(dual_result.original_result.evidence_chains),
        "translated_chain_count": len(dual_result.translated_result.evidence_chains),
        "original_evidence_item_count": len(dual_result.original_result.evidence_items),
        "translated_evidence_item_count": len(dual_result.translated_result.evidence_items),
        "refreshed_upstream": refreshed_upstream,
    }
    summary.update(
        build_summary_metadata(
            imported_terminology=imported_terminology,
            terminology_sources=terminology_sources,
            terminology_version=terminology_version,
            terminology_entry_count=terminology_entry_count,
            embedding_available=embedding_available,
        )
    )
    summary["terminology_root"] = str(terminology_root)
    return summary


async def run_standardize_entities(
    *,
    extract_evidence_dir: Path,
    output_dir: Path,
    service: EntityStandardizationService | Any | None = None,
    source_document_id: str | None = None,
    processing_run_id: str | None = None,
    run_id: str | None = None,
    terminology_root: Path = DEFAULT_TERMINOLOGY_ROOT,
    terminology_version: str | None = None,
    terminology_sources: list[str] | None = None,
    import_terminology: bool = False,
    refresh_upstream: bool = False,
    cross_lingual_input_dir: Path = DEFAULT_CROSS_LINGUAL_INPUT_DIR,
    refresh_run_id: str | None = None,
) -> Path:
    """Run deterministic Phase 3 standardization and save outputs."""
    cfg = get_config()
    extract_evidence_dir = extract_evidence_dir.resolve()
    output_dir = output_dir.resolve()
    terminology_root = terminology_root.resolve()
    cross_lingual_input_dir = cross_lingual_input_dir.resolve()
    terminology_sources = list(terminology_sources or DEFAULT_TERMINOLOGY_SOURCES)
    terminology_version = terminology_version or datetime.now().strftime("%Y-%m-%d")
    source_document_id = source_document_id or str(uuid4())
    processing_run_id = processing_run_id or str(uuid4())
    refresh_run_id = refresh_run_id or "latest"

    refreshed_dir = None
    if refresh_upstream:
        refreshed_dir = await _maybe_await(
            _refresh_upstream_if_requested(
                refresh_upstream=refresh_upstream,
                cross_lingual_input_dir=cross_lingual_input_dir,
                extract_output_dir=extract_evidence_dir.parent.parent,
                refresh_run_id=refresh_run_id,
            ),
        )
    if import_terminology:
        await _maybe_await(
            _import_terminology_if_requested(
                cfg=cfg,
                terminology_root=terminology_root,
                version=terminology_version,
                sources=terminology_sources,
            ),
        )

    effective_extract_evidence_dir = refreshed_dir or extract_evidence_dir
    dual_result = _read_dual_result(effective_extract_evidence_dir / "result.json")
    effective_run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_dir = output_dir / dual_result.document_id / effective_run_id

    session_resources = _open_standardization_session(cfg)
    if isinstance(session_resources, tuple):
        engine, session_factory = session_resources
    else:
        engine, session_factory = None, session_resources
    try:
        async with get_async_session(session_factory) as session:
            effective_service = service or EntityStandardizationService(cfg=cfg, session=session)
            result = await effective_service.run_dual_result(
                dual_result,
                source_document_id=source_document_id,
                processing_run_id=processing_run_id,
            )
            await session.commit()
    finally:
        if engine is not None:
            await engine.dispose()

    _write_json(saved_dir / "result.json", result)
    _write_json(saved_dir / "matches.json", {"matches": serialize_matches(result.matches)})
    _write_json(saved_dir / "upstream_result.json", dual_result)
    _write_json(
        saved_dir / "summary.json",
        _summary(
            standardization_result=result,
            dual_result=dual_result,
            extract_evidence_dir=effective_extract_evidence_dir,
            saved_dir=saved_dir,
            source_document_id=source_document_id,
            processing_run_id=processing_run_id,
            refreshed_upstream=refresh_upstream,
            imported_terminology=import_terminology,
            terminology_root=terminology_root,
            terminology_version=terminology_version,
            terminology_sources=terminology_sources,
        ),
    )
    logger.info(
        "Saved standardization outputs: document={}, standardized={}, ambiguous={}, unmapped={}",
        result.document_id,
        result.standardized_count,
        result.ambiguous_count,
        result.unmapped_count,
    )
    return saved_dir


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 3 standardization E2E")
    parser.add_argument("--extract-evidence-dir", type=Path, default=DEFAULT_EXTRACT_EVIDENCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--cross-lingual-input-dir", type=Path, default=DEFAULT_CROSS_LINGUAL_INPUT_DIR)
    parser.add_argument("--refresh-upstream", action="store_true")
    parser.add_argument("--refresh-run-id", default="latest")
    parser.add_argument("--import-terminology", action="store_true")
    parser.add_argument("--terminology-root", type=Path, default=DEFAULT_TERMINOLOGY_ROOT)
    parser.add_argument("--terminology-version", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--terminology-sources", nargs="+", default=list(DEFAULT_TERMINOLOGY_SOURCES))
    parser.add_argument("--source-document-id", default=None)
    parser.add_argument("--processing-run-id", default=None)
    parser.add_argument("--run-id", default=None)
    return parser.parse_args()


async def _main() -> None:
    _configure_logger()
    args = _parse_args()
    await run_standardize_entities(
        extract_evidence_dir=args.extract_evidence_dir,
        output_dir=args.output_dir,
        source_document_id=args.source_document_id,
        processing_run_id=args.processing_run_id,
        run_id=args.run_id,
        terminology_root=args.terminology_root,
        terminology_version=args.terminology_version,
        terminology_sources=args.terminology_sources,
        import_terminology=args.import_terminology,
        refresh_upstream=args.refresh_upstream,
        cross_lingual_input_dir=args.cross_lingual_input_dir,
        refresh_run_id=args.refresh_run_id,
    )


if __name__ == "__main__":
    asyncio.run(_main())
