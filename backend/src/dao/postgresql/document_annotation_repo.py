"""Repository for the ``document_annotations`` table.

Provides async CRUD over user-created text-selection annotations. Functions
mirror the style of :mod:`literature_profile_repo` and operate directly on an
``AsyncSession`` so callers control transaction boundaries.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.postgresql.models import DocumentAnnotation


async def list_annotations(
    session: AsyncSession,
    source_document_id: uuid.UUID,
    track: str | None = None,
) -> Sequence[DocumentAnnotation]:
    """Return annotations for a document, optionally filtered by track.

    Args:
        session: Async SQLAlchemy session.
        source_document_id: Parent source document UUID.
        track: Optional track filter ("original" or "translated").

    Returns:
        Sequence of ``DocumentAnnotation`` ORM rows ordered by creation time.
    """
    stmt = select(DocumentAnnotation).where(DocumentAnnotation.source_document_id == source_document_id)
    if track is not None:
        stmt = stmt.where(DocumentAnnotation.track == track)
    stmt = stmt.order_by(DocumentAnnotation.created_at, DocumentAnnotation.id)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_annotation(session: AsyncSession, annotation_id: uuid.UUID) -> DocumentAnnotation | None:
    """Fetch a single annotation by id, or None if not found."""
    stmt = select(DocumentAnnotation).where(DocumentAnnotation.id == annotation_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_annotation(
    session: AsyncSession,
    source_document_id: uuid.UUID,
    *,
    track: str,
    paragraph_id: str,
    start_offset: int,
    end_offset: int,
    color: str | None = None,
    note: str | None = None,
    author: str | None = None,
) -> DocumentAnnotation:
    """Insert a new annotation and return the persisted ORM row.

    Args:
        session: Async SQLAlchemy session.
        source_document_id: Parent source document UUID.
        track: "original" or "translated".
        paragraph_id: Rendered paragraph identifier.
        start_offset: Start character offset (>= 0).
        end_offset: End character offset (> start_offset).
        color: Optional hex color string.
        note: Optional free-text note.
        author: Optional author label.

    Returns:
        The freshly created ``DocumentAnnotation`` instance.
    """
    annotation = DocumentAnnotation(
        source_document_id=source_document_id,
        track=track,
        paragraph_id=paragraph_id,
        start_offset=start_offset,
        end_offset=end_offset,
        color=color,
        note=note,
        author=author,
    )
    session.add(annotation)
    await session.flush()
    await session.refresh(annotation)
    return annotation


async def update_annotation(
    session: AsyncSession,
    annotation_id: uuid.UUID,
    *,
    color: str | None = None,
    note: str | None = None,
    update_color: bool = False,
    update_note: bool = False,
) -> DocumentAnnotation | None:
    """Patch mutable fields (color, note) of an annotation.

    Only fields marked with their ``update_*`` flag are mutated. This lets the
    API distinguish omitted fields from explicit JSON ``null`` values.

    Args:
        session: Async SQLAlchemy session.
        annotation_id: UUID of the annotation to patch.
        color: New color value, or None to leave unchanged.
        note: New note value, or None to leave unchanged.
        update_color: Whether to persist the color value.
        update_note: Whether to persist the note value.

    Returns:
        Updated ``DocumentAnnotation`` or ``None`` if not found.
    """
    stmt = select(DocumentAnnotation).where(DocumentAnnotation.id == annotation_id)
    result = await session.execute(stmt)
    annotation = result.scalar_one_or_none()
    if annotation is None:
        return None
    if update_color:
        annotation.color = color
    if update_note:
        annotation.note = note
    await session.flush()
    await session.refresh(annotation)
    return annotation


async def delete_annotation(session: AsyncSession, annotation_id: uuid.UUID) -> bool:
    """Delete an annotation by id.

    Args:
        session: Async SQLAlchemy session.
        annotation_id: UUID of the annotation to delete.

    Returns:
        True if a row was deleted, False if no matching annotation existed.
    """
    stmt = delete(DocumentAnnotation).where(DocumentAnnotation.id == annotation_id)
    result = await session.execute(stmt)
    return (result.rowcount or 0) > 0
