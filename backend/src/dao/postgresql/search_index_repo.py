"""Flattened search index repository for fast front-end lookup.

Exposes a physical ``frontend_search_index`` table refreshed from the
``canonical_evidence_items`` plus document identifier tables.  The table
uses a unique index on ``canonical_evidence_id`` so that a future switch
to a materialized view with ``REFRESH MATERIALIZED VIEW CONCURRENTLY``
remains possible.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import (
    Column,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    or_,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

# ── Table definition ──────────────────────────────────────────────────────

GENE_IDS_PAYLOAD_KEY = "gene_ids"
VARIANT_IDS_PAYLOAD_KEY = "variant_ids"
ENTITY_IDS_PAYLOAD_KEY = "entity_ids"
SEARCH_TEXT_PAYLOAD_KEY = "search_text"

search_index_metadata = MetaData()

frontend_search_index = Table(
    "frontend_search_index",
    search_index_metadata,
    Column("id", Integer, primary_key=True),
    Column("canonical_evidence_id", UUID(as_uuid=True), nullable=False),
    Column("pmid", Text, nullable=True),
    Column("doi", Text, nullable=True),
    Column("gene_ids", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("variant_ids", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("entity_ids", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("field_id", String(128), nullable=False),
    Column("review_status", String(32), nullable=False),
    Column("current_best_confidence", Numeric(5, 4), nullable=True),
    Column("search_text", Text, nullable=False, server_default=text("''")),
    Column("active_payload", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Index(
        "ix_frontend_search_index_canonical_evidence_id",
        "canonical_evidence_id",
        unique=True,
    ),
)


# ── Repository ────────────────────────────────────────────────────────────


class SearchIndexRepository:
    """Read-optimised query surface for the front-end search bar.

    The caller owns the session lifecycle; this repository only executes
    queries within the provided session.
    """

    def __init__(self, session: Any) -> None:
        """Wrap an async SQLAlchemy session.

        The session parameter is typed as ``Any`` so mock-friendly test
        sessions can be passed alongside real ``AsyncSession`` instances.
        """
        self._session = session

    # ── Query ──────────────────────────────────────────────────────────

    async def search(
        self,
        *,
        gene_ids: list[str] | None = None,
        variant_ids: list[str] | None = None,
        doi: str | None = None,
        pmid: str | None = None,
        field_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:  # noqa  # dict-return: unstructured projection rows.
        """Return rows matching any of the provided search criteria.

        Search result rows are read-model projections with a flexible shape
        mirroring ``frontend_search_index`` columns.

        Returns an empty list when no filters are supplied.
        """
        conditions: list = []

        if gene_ids:
            # gene_ids is a JSONB array; use ?| overlap operator.
            conditions.append(
                frontend_search_index.c.gene_ids.op("?|")(gene_ids)
            )

        if variant_ids:
            conditions.append(
                frontend_search_index.c.variant_ids.op("?|")(variant_ids)
            )

        if doi is not None:
            conditions.append(frontend_search_index.c.doi == doi)

        if pmid is not None:
            conditions.append(frontend_search_index.c.pmid == pmid)

        if field_id is not None:
            conditions.append(frontend_search_index.c.field_id == field_id)

        if not conditions:
            return []

        query = (
            select(frontend_search_index)
            .where(or_(*conditions))
            .limit(limit)
        )

        result = await self._session.execute(query)
        rows = result.mappings().all()
        return [dict(row) for row in rows]

    # ── Refresh ────────────────────────────────────────────────────────

    async def refresh(self) -> None:
        """Truncate then rebuild the search index from canonical evidence."""
        await self._session.execute(
            text("TRUNCATE TABLE frontend_search_index")
        )

        await self._session.execute(
            text(f"""
                INSERT INTO frontend_search_index (
                    canonical_evidence_id,
                    pmid,
                    doi,
                    gene_ids,
                    variant_ids,
                    entity_ids,
                    field_id,
                    review_status,
                    current_best_confidence,
                    search_text,
                    active_payload
                )
                SELECT
                    cei.canonical_evidence_id,
                    sdi_pmid.identifier_value AS pmid,
                    sdi_doi.identifier_value AS doi,
                    COALESCE(
                        cei.active_payload -> '{GENE_IDS_PAYLOAD_KEY}',
                        '[]'::jsonb
                    ) AS gene_ids,
                    COALESCE(
                        cei.active_payload -> '{VARIANT_IDS_PAYLOAD_KEY}',
                        '[]'::jsonb
                    ) AS variant_ids,
                    COALESCE(
                        cei.active_payload -> '{ENTITY_IDS_PAYLOAD_KEY}',
                        '[]'::jsonb
                    ) AS entity_ids,
                    cei.field_id,
                    cei.review_status,
                    cei.current_best_confidence,
                    COALESCE(cei.active_payload ->> '{SEARCH_TEXT_PAYLOAD_KEY}', '') AS search_text,
                    cei.active_payload
                FROM canonical_evidence_items cei
                LEFT JOIN source_document_identifiers sdi_pmid
                    ON  sdi_pmid.source_document_id = cei.source_document_id
                    AND sdi_pmid.identifier_type = 'pmid'
                LEFT JOIN source_document_identifiers sdi_doi
                    ON  sdi_doi.source_document_id = cei.source_document_id
                    AND sdi_doi.identifier_type = 'doi'
            """),
        )

        await self._session.commit()
