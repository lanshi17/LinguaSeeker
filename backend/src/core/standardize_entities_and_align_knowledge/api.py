"""Public facade for Phase 3 entity standardization."""
from __future__ import annotations

import inspect
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
)
from src.core.standardize_entities_and_align_knowledge.adapters import DualResultAdapter
from src.core.standardize_entities_and_align_knowledge.contracts import (
    EntityMatch,
    EntityType,
    StandardizationResult,
)
from src.core.standardize_entities_and_align_knowledge.core import StandardizationService
from src.core.standardize_entities_and_align_knowledge.importers import (
    ImportBatch,
    build_clinvar_core_tsv,
    iter_clinvar_batches,
    parse_clingen_rows,
    parse_hgnc_rows,
    parse_hpo_rows,
    parse_omim_rows,
)
from src.core.standardize_entities_and_align_knowledge.matchers import HybridTerminologyMatcher
from src.core.standardize_entities_and_align_knowledge.precise_match.core import PreciseTerminologyMatcher
from src.core.standardize_entities_and_align_knowledge.repositories import (
    StandardizationRepository,
)
from src.core.standardize_entities_and_align_knowledge.similarity_match.core import (
    SimilarityMatchConfig,
    SimilarityTerminologyMatcher,
)
from src.core.standardize_entities_and_align_knowledge.similarity_match.providers import (
    ModelServerEmbeddingProvider,
    ModelServerRerankProvider,
)
from src.core.standardize_entities_and_align_knowledge.similarity_match.repositories import (
    PgvectorTerminologyRepository,
)
from src.dao.postgresql.connection import async_session_factory, build_async_engine, get_async_session

if TYPE_CHECKING:
    from src.core.config import Settings


def serialize_matches(matches: tuple[EntityMatch, ...]) -> list[dict[str, Any]]:
    """Serialize EntityMatch tuple into auditable JSON-serializable dicts."""
    entries: list[dict[str, Any]] = []
    for match in matches:
        entry: dict[str, Any] = {
            "candidate_id": match.candidate.candidate_id,
            "raw_text": match.candidate.raw_text,
            "entity_type": match.candidate.entity_type.value,
            "chain_id": match.candidate.chain_id,
            "track": match.candidate.track,
            "field_id": match.candidate.field_id,
            "status": match.status.value,
            "external_id": match.external_id,
            "display_name": match.display_name,
            "rationale": match.rationale,
            "match_method": match.match_method.value,
            "similarity_score": match.similarity_score,
        }
        if match.terminology_candidates:
            entry["terminology_candidates"] = [
                {
                    "external_id": tc.external_id,
                    "display_name": tc.display_name,
                    "source_db": tc.source_db,
                    "alias_type": tc.alias_type,
                }
                for tc in match.terminology_candidates
            ]
        entries.append(entry)
    return entries


def build_summary_metadata(
    *,
    imported_terminology: bool,
    terminology_sources: list[str],
    terminology_version: str,
    terminology_entry_count: int = 0,
    embedding_available: bool = False,
) -> dict[str, Any]:
    """Build truthful summary metadata with terminology health indicators."""
    return {
        "imported_terminology": imported_terminology,
        "terminology_sources": terminology_sources,
        "terminology_version": terminology_version,
        "terminology_entry_count": terminology_entry_count,
        "embedding_available": embedding_available,
    }


class EntityStandardizationService:
    """Facade that wires the adapter, matcher, and orchestration service."""

    def __init__(self, cfg: Settings):
        self._cfg = cfg

    async def run_dual_result(
        self,
        session: AsyncSession,
        result: DualEvidenceExtractionResult,
        *,
        source_document_id: str,
        processing_run_id: str,
    ) -> StandardizationResult:
        """Standardize one dual-track evidence extraction result."""
        repository = StandardizationRepository(session)
        precise_matcher = PreciseTerminologyMatcher(repository)
        semantic_base_url = self._cfg.embedding.base_url or self._cfg.model_server_url
        similarity_matcher = SimilarityTerminologyMatcher(
            embedding_provider=ModelServerEmbeddingProvider(
                base_url=semantic_base_url,
                model=self._cfg.embedding.model,
            ),
            rerank_provider=ModelServerRerankProvider(
                base_url=self._cfg.rerank.base_url or self._cfg.model_server_url,
                model=self._cfg.rerank.model,
            ),
            repository=PgvectorTerminologyRepository(session),
            config=SimilarityMatchConfig(
                embedding_model=self._cfg.embedding.model,
                rerank_top_k=self._cfg.rerank.top_k,
                rerank_score_threshold=self._cfg.rerank.score_threshold,
            ),
        )
        matcher = HybridTerminologyMatcher(precise_matcher, similarity_matcher)
        adapter = DualResultAdapter()
        input_data = adapter.to_standardization_input(
            result,
            source_document_id=source_document_id,
            processing_run_id=processing_run_id,
        )
        return await StandardizationService(matcher, repository).run(input_data)


async def _maybe_await(value: Any) -> Any:
    """Await helper results only when they are actually awaitable."""
    if inspect.isawaitable(value):
        return await value
    return value


async def import_terminology(
    *,
    cfg: Any,
    terminology_root: Path,
    version: str,
    sources: list[str],
) -> None:
    """Import local terminology sources through the repository facade."""
    started_at = time.perf_counter()
    source_names = tuple(source.lower() for source in sources)
    logger.info(
        "Starting terminology import: root={}, version={}, sources={}",
        terminology_root,
        version,
        list(source_names),
    )
    batches = _load_import_batches(terminology_root=terminology_root, version=version, sources=source_names)
    total_entries = sum(len(batch.entries) for batch in batches)
    total_aliases = sum(len(batch.aliases) for batch in batches)
    total_relationships = sum(len(batch.relationships) for batch in batches)
    logger.info(
        "Parsed terminology batches: batches={}, entries={}, aliases={}, relationships={}",
        len(batches),
        total_entries,
        total_aliases,
        total_relationships,
    )
    engine = build_async_engine(cfg)
    session_factory = async_session_factory(engine)
    try:
        async with get_async_session(session_factory) as session:
            repository = StandardizationRepository(session)
            for index, batch in enumerate(batches, start=1):
                source_db = _describe_batch_source(batch)
                logger.info(
                    "Importing batch {}/{} [{}]: entries={}, aliases={}, relationships={}",
                    index,
                    len(batches),
                    source_db,
                    len(batch.entries),
                    len(batch.aliases),
                    len(batch.relationships),
                )
                await repository.upsert_terminology_batch(batch)
                logger.info("Imported batch {}/{} [{}]", index, len(batches), source_db)
            if "clinvar" in source_names:
                clinvar_path = _ensure_clinvar_core_path(Path(terminology_root) / "clinvar" / "variant_summary.txt")
                await _maybe_await(
                    _import_clinvar_stream(
                        repository=repository,
                        path=clinvar_path,
                        version=version,
                        chunk_size=10_000,
                    ),
                )
            await session.commit()
            logger.info("Committed terminology import transaction")
    finally:
        await engine.dispose()
    logger.info("Terminology import completed in {:.2f}s", time.perf_counter() - started_at)


async def build_terminology_embeddings(
    *,
    cfg: Any,
    entity_types: set[EntityType] | None = None,
    source_dbs: set[str] | None = None,
) -> int:
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
                entity_types=entity_types,
                source_dbs=source_dbs,
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
        batches.append(parse_hgnc_rows(source_root / "hgnc" / "hgnc_complete_set.txt", version=version))
    if "omim" in sources:
        batches.append(parse_omim_rows(source_root / "omim", version=version))
    if "hpo" in sources:
        batches.append(parse_hpo_rows(source_root / "hpo", version=version))
    if "clingen" in sources:
        batches.append(parse_clingen_rows(source_root / "clingen", version=version))

    return tuple(batches)


def _describe_batch_source(batch: ImportBatch) -> str:
    """Return a human-readable source label for one parsed batch."""
    if batch.entries:
        return batch.entries[0].source_db
    if batch.aliases:
        return batch.aliases[0].source_db
    if batch.relationships:
        return batch.relationships[0].source_db
    return "empty"


async def _import_clinvar_stream(
    *,
    repository: StandardizationRepository,
    path: Path,
    version: str,
    chunk_size: int,
) -> None:
    """Import ClinVar in bounded chunks to avoid monolithic memory growth."""
    logger.info("Streaming ClinVar import: path={}, chunk_size={}", path, chunk_size)
    chunk_count = 0
    total_entries = 0
    total_aliases = 0
    total_relationships = 0
    for chunk_count, batch in enumerate(
        iter_clinvar_batches(path=path, version=version, chunk_size=chunk_size),
        start=1,
    ):
        total_entries += len(batch.entries)
        total_aliases += len(batch.aliases)
        total_relationships += len(batch.relationships)
        logger.info(
            "Importing ClinVar chunk {}: entries={}, aliases={}, relationships={}",
            chunk_count,
            len(batch.entries),
            len(batch.aliases),
            len(batch.relationships),
        )
        await repository.upsert_terminology_batch(batch)
        await repository.session.commit()
    logger.info(
        "Completed ClinVar streaming import: chunks={}, entries={}, aliases={}, relationships={}",
        chunk_count,
        total_entries,
        total_aliases,
        total_relationships,
    )


def _ensure_clinvar_core_path(path: Path) -> Path:
    """Return the reduced ClinVar TSV path, generating it from raw export when needed."""
    core_path = path.with_name("variant_summary.core.tsv")
    if core_path.exists() and core_path.stat().st_mtime >= path.stat().st_mtime:
        return core_path
    logger.info("Building ClinVar core TSV: source={}, target={}", path, core_path)
    rows_written = build_clinvar_core_tsv(path, core_path)
    logger.info("Built ClinVar core TSV: rows={}", rows_written)
    return core_path
