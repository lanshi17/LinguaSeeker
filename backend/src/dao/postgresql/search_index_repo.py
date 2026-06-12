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
    DateTime,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    cast,
    func,
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
    Column("gene_ids", JSONB, nullable=False, server_default=text("'[]'")),
    Column("variant_ids", JSONB, nullable=False, server_default=text("'[]'")),
    Column("entity_ids", JSONB, nullable=False, server_default=text("'[]'")),
    Column("field_id", String(128), nullable=False),
    Column("review_status", String(32), nullable=False),
    Column("current_best_confidence", Numeric(5, 4), nullable=True),
    Column("search_text", Text, nullable=False, server_default=text("''")),
    Column("active_payload", JSONB, nullable=False, server_default=text("'{}'")),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Index(
        "ix_frontend_search_index_canonical_evidence_id",
        "canonical_evidence_id",
        unique=True,
    ),
    Index("ix_frontend_search_index_pmid", "pmid"),
    Index("ix_frontend_search_index_doi", "doi"),
    Index("ix_frontend_search_index_gene_ids", "gene_ids", postgresql_using="gin"),
    Index("ix_frontend_search_index_variant_ids", "variant_ids", postgresql_using="gin"),
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
        gene: str | None = None,
        variant: str | None = None,
        disease: str | None = None,
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

        When no filters are supplied, returns all rows (default list view).
        """
        conditions: list = []

        if gene:
            # Text search on active_payload->>'gene' (case-insensitive).
            conditions.append(
                cast(
                    frontend_search_index.c.active_payload["gene"], Text
                ).ilike(f"%{gene}%")
            )

        if variant:
            conditions.append(
                cast(
                    frontend_search_index.c.active_payload["variant"], Text
                ).ilike(f"%{variant}%")
            )

        if disease:
            conditions.append(
                cast(
                    frontend_search_index.c.active_payload["disease"], Text
                ).ilike(f"%{disease}%")
            )

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

        # When no filters are supplied, return all rows (default list view).
        stmt = select(frontend_search_index)
        if conditions:
            stmt = stmt.where(or_(*conditions))
        query = stmt.order_by(frontend_search_index.c.pmid).limit(limit)

        result = await self._session.execute(query)
        rows = result.mappings().all()
        return [dict(row) for row in rows]

    # ── Refresh ────────────────────────────────────────────────────────

    async def refresh(self) -> None:
        """Truncate then rebuild the search index from canonical evidence."""
        try:
            await self._session.execute(
                text("DELETE FROM frontend_search_index")
            )
        except Exception:
            # Table may not exist in SQLite test environments
            return

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
                    active_payload,
                    created_at
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
                    cei.active_payload,
                    cei.created_at
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
