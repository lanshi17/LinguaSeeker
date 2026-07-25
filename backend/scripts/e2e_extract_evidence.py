"""Run extract_evidence E2E over persisted original/translated JSON outputs.

Usage:
    cd backend

    uv run python scripts/e2e_extract_evidence.py
    uv run python scripts/e2e_extract_evidence.py --input-dir output/zh/法布雷病1例
    uv run python scripts/e2e_extract_evidence.py --output-dir output/extract_evidence
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from loguru import logger
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import get_config
from src.core.evidence_extraction.api import EvidenceExtractionService
from src.core.evidence_extraction.contracts import (
    DualEvidenceExtractionResult,
    DualTrackDocuments,
    EvidenceExtractionResult,
    EvidenceStatus,
)


BACKEND_DIR = Path(__file__).resolve().parents[1]
LEGACY_FABRY_INPUT_DIR = BACKEND_DIR / "output" / "zh" / "法布雷病1例"
CROSS_LINGUAL_FABRY_INPUT_DIR = BACKEND_DIR / "output" / "cross_lingual" / "zh" / "法布雷病1例"
DEFAULT_INPUT_DIR = LEGACY_FABRY_INPUT_DIR if LEGACY_FABRY_INPUT_DIR.exists() else CROSS_LINGUAL_FABRY_INPUT_DIR
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "output" / "extract_evidence"


class DualEvidenceService(Protocol):
    async def run_dual(self, documents: DualTrackDocuments) -> DualEvidenceExtractionResult:
        """Run original and translated evidence extraction."""


def _configure_logger() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")


def _ensure_evidence_env_from_llm() -> None:
    """Map fast/reasoning LLM settings to EVIDENCE_EXTRACTION_* for this process only."""
    try:
        cfg = get_config()
        cfg_llm = cfg.llm
        cfg_reasoning = getattr(cfg, "reasoning", None)
    except Exception:
        cfg_llm = None
        cfg_reasoning = None
    mappings = {
        "EVIDENCE_EXTRACTION_API_KEY": (
            ("FAST_LLM_API_KEY", "LLM_API_KEY"),
            cfg_llm,
            "api_key",
        ),
        "EVIDENCE_EXTRACTION_BASE_URL": (
            ("FAST_LLM_BASE_URL", "LLM_BASE_URL"),
            cfg_llm,
            "base_url",
        ),
        "EVIDENCE_EXTRACTION_FAST_MODEL": (
            ("FAST_LLM_MODEL", "LLM_MODEL"),
            cfg_llm,
            "model",
        ),
        "EVIDENCE_EXTRACTION_STANDARD_MODEL": (
            ("FAST_LLM_MODEL", "LLM_MODEL"),
            cfg_llm,
            "model",
        ),
        "EVIDENCE_EXTRACTION_STRONG_MODEL": (
            ("REASONING_LLM_MODEL", "FAST_LLM_MODEL", "LLM_MODEL"),
            cfg_reasoning if cfg_reasoning is not None and getattr(cfg_reasoning, "model", "") else cfg_llm,
            "model",
        ),
    }
    for evidence_key, (env_keys, cfg_obj, cfg_attr) in mappings.items():
        if os.environ.get(evidence_key):
            continue
        for env_key in env_keys:
            if os.environ.get(env_key):
                os.environ[evidence_key] = os.environ[env_key]
                break
        if os.environ.get(evidence_key):
            continue
        cfg_value = getattr(cfg_obj, cfg_attr, "") if cfg_obj is not None else ""
        if cfg_value:
            os.environ[evidence_key] = cfg_value


def _json_ready(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _write_json(path: Path, data: BaseModel | dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_ready(data), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _track_summary(result: EvidenceExtractionResult) -> dict[str, Any]:
    report = result.quality_report
    if report is None:
        found_count = sum(1 for item in result.evidence_items if item.status == EvidenceStatus.FOUND)
        not_found_count = sum(1 for item in result.evidence_items if item.status == EvidenceStatus.NOT_FOUND)
        source_invalid_count = sum(1 for item in result.evidence_items if item.status == EvidenceStatus.SOURCE_INVALID)
        ocr_gap_count = sum(1 for item in result.evidence_items if item.status == EvidenceStatus.OCR_GAP)
        table_ungrounded_count = sum(
            1 for item in result.evidence_items if item.status == EvidenceStatus.TABLE_UNGROUNDED
        )
        ambiguous_count = sum(
            1
            for item in result.evidence_items
            if item.source is not None and item.source.source_precision.value == "ambiguous"
        )
    else:
        found_count = report.found_count
        not_found_count = report.not_found_count
        source_invalid_count = report.source_invalid_count
        ocr_gap_count = report.ocr_gap_count
        table_ungrounded_count = report.table_ungrounded_count
        ambiguous_count = report.ambiguous_source_count
    group_ids = sorted({item.group_id for item in result.evidence_items if item.group_id})
    chain_levels: dict[str, int] = {}
    case_ids = sorted({case_id for chain in result.evidence_chains for case_id in chain.case_ids})
    special_evidence_ids = sorted(
        {special_id for chain in result.evidence_chains for special_id in chain.special_evidence_ids}
    )
    for chain in result.evidence_chains:
        chain_levels[chain.chain_level] = chain_levels.get(chain.chain_level, 0) + 1
    grounded_source_count = sum(1 for item in result.evidence_items if item.source is not None)
    raw_source_count = sum(1 for item in result.evidence_items if item.raw_source is not None)
    block_grounded_source_count = sum(
        1 for item in result.evidence_items if item.source is not None and item.source.block_index >= 0
    )
    source_precision_counts: dict[str, int] = {}
    for item in result.evidence_items:
        if item.source is None:
            continue
        precision = item.source.source_precision.value
        source_precision_counts[precision] = source_precision_counts.get(precision, 0) + 1
    assigned_acmg_codes = sorted({code for item in result.evidence_items for code in item.assigned_acmg_codes})
    assigned_clingen_modules = sorted(
        {module for item in result.evidence_items for module in item.assigned_clingen_modules}
    )
    return {
        "status": result.status.value,
        "track": result.track.value,
        "evidence_item_count": len(result.evidence_items),
        "group_count": len(group_ids),
        "found_count": found_count,
        "not_found_count": not_found_count,
        "source_invalid_count": source_invalid_count,
        "ocr_gap_count": ocr_gap_count,
        "table_ungrounded_count": table_ungrounded_count,
        "ambiguous_source_count": ambiguous_count,
        "special_evidence_count": len(result.special_evidence),
        "chain_levels": chain_levels,
        "case_ids": case_ids,
        "special_evidence_ids": special_evidence_ids,
        "grounded_source_count": grounded_source_count,
        "raw_source_count": raw_source_count,
        "block_grounded_source_count": block_grounded_source_count,
        "source_precision_counts": source_precision_counts,
        "external_completion_required_count": sum(
            1 for item in result.evidence_items if item.requires_external_completion
        ),
        "assigned_acmg_codes": assigned_acmg_codes,
        "assigned_clingen_modules": assigned_clingen_modules,
        "quality_passed": report.passed if report else None,
        "quality_scorable": report.scorable if report else None,
        "score_gate_passed": report.score_gate_passed if report else None,
        "human_review_required": report.human_review_required if report else None,
        "human_review_reasons": report.human_review_reasons if report else [],
        "human_review_by_category": report.human_review_by_category if report else {},
    }


def _summary(result: DualEvidenceExtractionResult, input_dir: Path, saved_dir: Path) -> dict[str, Any]:
    return {
        "document_id": result.document_id,
        "input_dir": str(input_dir),
        "output_dir": str(saved_dir),
        "created_at": datetime.now().isoformat(),
        "original": _track_summary(result.original_result),
        "translated": _track_summary(result.translated_result),
    }


async def run_extract_evidence(
    input_dir: Path,
    output_dir: Path,
    service: DualEvidenceService | None = None,
    run_id: str | None = None,
) -> Path:
    """Run dual-track extraction and save full plus per-track outputs."""
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    documents = EvidenceExtractionService.build_dual_documents_from_output_dir(input_dir)
    if service is None:
        _ensure_evidence_env_from_llm()
        get_config.cache_clear()
        service = EvidenceExtractionService(cfg=get_config())

    effective_run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_dir = output_dir / documents.document_id / effective_run_id

    logger.info("Running extract_evidence: input={}, output={}", input_dir, saved_dir)
    result = await service.run_dual(documents)

    _write_json(saved_dir / "result.json", result)
    _write_json(saved_dir / "original_result.json", result.original_result)
    _write_json(saved_dir / "translated_result.json", result.translated_result)
    _write_json(saved_dir / "summary.json", _summary(result, input_dir, saved_dir))

    original_summary = _track_summary(result.original_result)
    translated_summary = _track_summary(result.translated_result)
    logger.info(
        "Saved extract_evidence outputs: original_found={}, translated_found={}",
        original_summary["found_count"],
        translated_summary["found_count"],
    )
    return saved_dir


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run extract_evidence E2E over persisted cross-lingual output")
    parser.add_argument(
        "--input-dir",
        default=str(DEFAULT_INPUT_DIR),
        help=f"Directory containing original.json and translated.json (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Directory where extraction results are saved (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional stable run id; defaults to timestamp",
    )
    return parser.parse_args()


async def _main() -> None:
    _configure_logger()
    args = _parse_args()
    saved_dir = await run_extract_evidence(
        input_dir=Path(args.input_dir),
        output_dir=Path(args.output_dir),
        run_id=args.run_id,
    )
    logger.info("Output directory: {}", saved_dir)


if __name__ == "__main__":
    asyncio.run(_main())
