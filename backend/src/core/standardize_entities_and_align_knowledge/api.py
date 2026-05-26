"""Public facade for Phase 3 entity standardization."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
)
from src.core.standardize_entities_and_align_knowledge.adapters import DualResultAdapter
from src.core.standardize_entities_and_align_knowledge.contracts import (
    StandardizationResult,
)
from src.core.standardize_entities_and_align_knowledge.core import StandardizationService
from src.core.standardize_entities_and_align_knowledge.importers import (
    ImportBatch,
    parse_clingen_rows,
    parse_clinvar_rows,
    parse_hgnc_rows,
    parse_hpo_rows,
    parse_omim_rows,
)
from src.core.standardize_entities_and_align_knowledge.matchers import TerminologyMatcher
from src.core.standardize_entities_and_align_knowledge.repositories import (
    StandardizationRepository,
)
from src.dao.connection import async_session_factory, build_async_engine, get_async_session


class EntityStandardizationService:
    """Facade that wires the adapter, matcher, and orchestration service."""

    def __init__(self, cfg: Any, session: Any):
        self._cfg = cfg
        self._session = session

    async def run_dual_result(
        self,
        result: DualEvidenceExtractionResult,
        *,
        source_document_id: str,
        processing_run_id: str,
    ) -> StandardizationResult:
        """Standardize one dual-track evidence extraction result."""
        repository = StandardizationRepository(self._session)
        matcher = TerminologyMatcher(repository)
        adapter = DualResultAdapter()
        input_data = adapter.to_standardization_input(
            result,
            source_document_id=source_document_id,
            processing_run_id=processing_run_id,
        )
        return await StandardizationService(matcher, repository).run(input_data)


async def import_terminology(
    *,
    cfg: Any,
    terminology_root: Path,
    version: str,
    sources: list[str],
) -> None:
    """Import local terminology sources through the repository facade."""
    source_names = tuple(source.lower() for source in sources)
    batches = _load_import_batches(terminology_root=terminology_root, version=version, sources=source_names)
    engine = build_async_engine(cfg)
    session_factory = async_session_factory(engine)
    try:
        async with get_async_session(session_factory) as session:
            repository = StandardizationRepository(session)
            for batch in batches:
                await repository.upsert_terminology_batch(batch)
            await session.commit()
    finally:
        await engine.dispose()


async def build_terminology_embeddings(*, cfg: Any) -> int:
    """Build pgvector embeddings for imported terminology entries."""
    from src.core.standardize_entities_and_align_knowledge.similarity_match.indexer import (
        TerminologyEmbeddingIndexer,
    )
    from src.core.standardize_entities_and_align_knowledge.similarity_match.providers import (
        ModelServerEmbeddingProvider,
    )

    engine = build_async_engine(cfg)
    session_factory = async_session_factory(engine)
    try:
        async with get_async_session(session_factory) as session:
            provider = ModelServerEmbeddingProvider(
                base_url=(cfg.embedding.base_url or cfg.model_server_url),
                model=cfg.embedding.model,
            )
            count = await TerminologyEmbeddingIndexer(session, provider).build(
                embedding_model=cfg.embedding.model,
                batch_size=cfg.embedding.batch_size,
            )
            await session.commit()
            return count
    finally:
        await engine.dispose()


def _load_import_batches(
    *,
    terminology_root: Path,
    version: str,
    sources: tuple[str, ...],
) -> tuple[ImportBatch, ...]:
    """Load parsed import batches for the selected source set."""
    batches: list[ImportBatch] = []
    source_root = Path(terminology_root)

    if "hgnc" in sources:
        batches.append(parse_hgnc_rows(source_root / "hgnc_complete_set.txt", version=version))
    if "omim" in sources:
        batches.append(parse_omim_rows(source_root / "omim", version=version))
    if "hpo" in sources:
        batches.append(parse_hpo_rows(source_root / "hpo", version=version))
    if "clingen" in sources:
        batches.append(parse_clingen_rows(source_root / "clingen", version=version))
    if "clinvar" in sources:
        batches.append(parse_clinvar_rows(source_root / "clinvar" / "variant_summary.txt", version=version))

    return tuple(batches)
