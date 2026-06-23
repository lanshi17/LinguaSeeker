"""Phase 2 adapter: translation and dual-track evidence extraction.

Uses TranslationService.run() + .save() for translation.
Uses EvidenceExtractionService.build_dual_documents_from_output_dir() + .run_dual()
for dual-track evidence extraction.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
from loguru import logger

from src.agents.contracts import (
    Phase2Output,
    PhaseStatus,
    PhaseStatusDetail,
    PipelineGraphState,
    PermanentPhaseError,
    RetryablePhaseError,
    SkipPhase3Reason,
    build_retryable_errors,
)
from src.core.cross_lingual_process_and_extract_evidence.contracts import CrossLingualOutput
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
    EvidenceExtractionService,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceExtractionStatus,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction import (
    CatalogExtractionError,
)

if TYPE_CHECKING:
    from src.core.cross_lingual_process_and_extract_evidence.workflow import (
        TranslationService,
    )

_RETRYABLE_ERRORS = build_retryable_errors() + (CatalogExtractionError,)
# FileNotFoundError/PermissionError are OSError subclasses but are permanent,
# not transient — must not be retried.
_PERMANENT_OS_ERRORS = (FileNotFoundError, PermissionError, IsADirectoryError)


def _load_blocks_from_json(json_path: str) -> list[dict] | None:
    """Load block dicts from a persisted Phase 2 JSON file."""
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    blocks = data.get("blocks")
    return blocks if isinstance(blocks, list) and blocks else None


class Phase2Adapter:
    """Thin adapter wrapping TranslationService + EvidenceExtractionService.

    Flow:
    1. Read parsed content from Phase 1 output_dir
    2. Call TranslationService.run() -> TranslationResult
    3. Call TranslationService.save() -> CrossLingualOutput
    4. Call build_dual_documents_from_output_dir() -> DualTrackDocuments
    5. Call EvidenceExtractionService.run_dual() -> DualEvidenceExtractionResult
    """

    def __init__(
        self,
        translation_service: TranslationService,
        extraction_service: EvidenceExtractionService,
    ):
        self._translation = translation_service
        self._extraction = extraction_service

    async def run(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 2: translate and extract dual-track evidence.

        Returns updated state with phase_2_output set on success.
        Sets skip_phase_3_reason if both tracks are NOT_RELEVANT.
        Raises RetryablePhaseError or PermanentPhaseError on failure.
        """
        logger.info("Phase 2 started: run={}", state.processing_run_id)

        state.phase_2_status = PhaseStatusDetail(
            status=PhaseStatus.RUNNING,
            started_at=datetime.now().isoformat(),
        )

        try:
            # Load parsed document from Phase 1 output
            if state.phase_1_output is None:
                raise PermanentPhaseError(
                    "Phase 1 output not found in state",
                    phase=2,
                )

            # Read from Phase 1 metadata (contains pages and content_blocks)
            metadata_path = state.phase_1_output.metadata_path
            async with aiofiles.open(metadata_path, "r") as f:
                content = await f.read()
                parse_data = json.loads(content)

            pages = parse_data.get("pages", [])
            content_blocks = parse_data.get("content_blocks", [])

            # Use absolute path to survive CWD changes
            from pathlib import Path as _Path
            _backend_root = _Path(__file__).resolve().parent.parent.parent
            output_dir = str(_backend_root / "data" / "pipeline" / state.processing_run_id / "phase_2")
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            # On retry, check if translation output already exists on disk
            doc_output_dir = Path(output_dir) / state.source_document_id
            existing_original = doc_output_dir / "original.json"
            existing_metadata = doc_output_dir / "metadata.json"
            cross_lingual_output = None
            translation_result = None

            if existing_original.exists() and existing_metadata.exists():
                logger.info("Phase 2 retry: translation output already exists, skipping translation")
                # Read source_language from persisted metadata
                async with aiofiles.open(existing_metadata, "r") as mf:
                    meta_content = await mf.read()
                    meta_data = json.loads(meta_content)
                source_lang = meta_data.get("source_language", "unknown")
                cross_lingual_output = CrossLingualOutput(
                    formatted_original="",
                    translated_english="",
                    source_language=source_lang,
                    terminology_map=meta_data.get("terminology_map", {}),
                    translation_warnings=meta_data.get("translation_warnings", []),
                    output_dir=str(doc_output_dir),
                    original_json_path=str(existing_original),
                    translated_json_path=str(doc_output_dir / "translated.json"),
                    image_paths=[],
                )

            if cross_lingual_output is None:
                # Run translation
                translation_result = await self._translation.run(
                    pages=pages,
                    content_blocks=content_blocks,
                )

                # Save translation output (creates original.json and translated.json)
                cross_lingual_output = await asyncio.to_thread(
                    self._translation.save,
                    result=translation_result,
                    output_dir=output_dir,
                    doc_id=state.source_document_id,
                )

            # Build dual documents using the service's static method
            # This reads from cross_lingual_output.output_dir (sync Path.read_text)
            dual_documents = await asyncio.to_thread(
                EvidenceExtractionService.build_dual_documents_from_output_dir,
                cross_lingual_output.output_dir,
                state.extraction_target,
            )

            # Run dual-track extraction via the service facade
            dual_result = await self._extraction.run_dual(dual_documents)

            # Check if document is relevant
            both_not_relevant = (
                dual_result.original_result.status
                == EvidenceExtractionStatus.NOT_RELEVANT
                and dual_result.translated_result.status
                == EvidenceExtractionStatus.NOT_RELEVANT
            )

            if both_not_relevant:
                logger.info("Document not relevant, setting skip_phase_3_reason")
                state.skip_phase_3_reason = SkipPhase3Reason.NOT_RELEVANT

            # Save extraction result for Phase 3 (N7 fix)
            extraction_result_path = f"{output_dir}/extraction_result.json"
            async with aiofiles.open(extraction_result_path, "w") as f:
                await f.write(json.dumps(dual_result.model_dump(mode="json")))

            # Persist document text and structured blocks while files are
            # guaranteed to exist on disk. Blocks enable structured rendering
            # (headings, tables, lists) in the evidence detail viewer.
            from src.agents.state_persistence import load_phase2_text_from_paths
            original_text, translated_doc_text = load_phase2_text_from_paths(
                cross_lingual_output.original_json_path,
                cross_lingual_output.translated_json_path,
            )

            # Capture structured blocks from translation result or disk
            original_blocks_dicts: list[dict] | None = None
            translated_blocks_dicts: list[dict] | None = None
            if translation_result is not None:
                if translation_result.original_blocks:
                    original_blocks_dicts = [b.to_dict() for b in translation_result.original_blocks]
                if translation_result.translated_blocks:
                    translated_blocks_dicts = [b.to_dict() for b in translation_result.translated_blocks]
            else:
                # Retry path: load blocks from persisted JSON files
                original_blocks_dicts = _load_blocks_from_json(cross_lingual_output.original_json_path)
                translated_blocks_dicts = _load_blocks_from_json(cross_lingual_output.translated_json_path)

            state.phase_2_output = Phase2Output(
                output_dir=cross_lingual_output.output_dir,
                original_json_path=cross_lingual_output.original_json_path,
                translated_json_path=cross_lingual_output.translated_json_path,
                source_language=cross_lingual_output.source_language,
                extraction_result_path=extraction_result_path,
                original_text=original_text,
                translated_text=translated_doc_text,
                original_blocks=original_blocks_dicts,
                translated_blocks=translated_blocks_dicts,
            )

            state.phase_2_status = PhaseStatusDetail(
                status=PhaseStatus.COMPLETED,
                started_at=state.phase_2_status.started_at,
                completed_at=datetime.now().isoformat(),
                duration_seconds=(
                    datetime.now() - datetime.fromisoformat(state.phase_2_status.started_at)
                ).total_seconds()
                if state.phase_2_status.started_at
                else None,
                summary={
                    "relevant": not both_not_relevant,
                    "source_language": cross_lingual_output.source_language,
                    "target_gene": state.extraction_target.gene_symbol if state.extraction_target else None,
                },
            )
            logger.info(
                "Phase 2 completed: run={}, skip_phase_3_reason={}",
                state.processing_run_id,
                state.skip_phase_3_reason,
            )
            return state

        except _PERMANENT_OS_ERRORS as e:
            raise PermanentPhaseError(
                f"Phase 2 permanent file error: {e}",
                phase=2,
            ) from e

        except _RETRYABLE_ERRORS as e:
            raise RetryablePhaseError(
                f"Phase 2 transient error: {e}",
                phase=2,
            ) from e

        except (PermanentPhaseError, RetryablePhaseError):
            raise  # Already classified, pass through

        except Exception as e:
            raise PermanentPhaseError(
                f"Phase 2 unexpected error: {e}",
                phase=2,
            ) from e
