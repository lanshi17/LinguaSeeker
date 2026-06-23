"""Document annotation CRUD routes.

Exposes per-document user text-selection annotations under
``/api/v1/documents/{source_document_id}/annotations``. The backend stores
raw character offsets without interpreting the coordinate system — the
frontend owns offset semantics (flattened ``textContent`` of a rendered
paragraph).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import require_api_key
from src.api.deps import get_db_session
from src.dao.postgresql import document_annotation_repo as repo

router = APIRouter()


# ── Pydantic contracts ───────────────────────────────────────────────────────


class AnnotationCreateRequest(BaseModel):
    """Request body for creating a new annotation."""

    track: Literal["original", "translated"]
    paragraph_id: str
    start_offset: int
    end_offset: int
    color: str | None = None
    note: str | None = None
    author: str | None = None

    @field_validator("end_offset")
    @classmethod
    def _end_after_start(cls, end_offset: int, info) -> int:  # type: ignore[no-untyped-def]
        """Ensure end_offset > start_offset >= 0."""
        start_offset = info.data.get("start_offset")
        if start_offset is None:
            return end_offset
        if start_offset < 0:
            raise ValueError("start_offset must be >= 0")
        if end_offset <= start_offset:
            raise ValueError("end_offset must be greater than start_offset")
        return end_offset

    @field_validator("start_offset")
    @classmethod
    def _start_non_negative(cls, start_offset: int) -> int:
        """Ensure start_offset >= 0 (also re-checked in end validator)."""
        if start_offset < 0:
            raise ValueError("start_offset must be >= 0")
        return start_offset


class AnnotationUpdateRequest(BaseModel):
    """Request body for patching an annotation (partial update)."""

    color: str | None = None
    note: str | None = None


class AnnotationResponse(BaseModel):
    """Serialized annotation row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_document_id: UUID
    track: str
    paragraph_id: str
    start_offset: int
    end_offset: int
    color: str | None
    note: str | None
    author: str | None
    created_at: datetime
    updated_at: datetime


class AnnotationListResponse(BaseModel):
    """Paginated-less list wrapper for annotations."""

    items: list[AnnotationResponse]


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get(
    "/{source_document_id}/annotations",
    response_model=AnnotationListResponse,
)
async def list_annotations(
    source_document_id: UUID,
    track: str | None = Query(default=None, description="Filter by track (original|translated)"),
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> AnnotationListResponse:
    """List annotations for a document, optionally filtered by track."""
    rows = await repo.list_annotations(session, source_document_id, track=track)
    return AnnotationListResponse(items=[AnnotationResponse.model_validate(r) for r in rows])


@router.post(
    "/{source_document_id}/annotations",
    response_model=AnnotationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_annotation(
    source_document_id: UUID,
    body: AnnotationCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> AnnotationResponse:
    """Create a new annotation on a document paragraph."""
    annotation = await repo.create_annotation(
        session,
        source_document_id,
        track=body.track,
        paragraph_id=body.paragraph_id,
        start_offset=body.start_offset,
        end_offset=body.end_offset,
        color=body.color,
        note=body.note,
        author=body.author,
    )
    return AnnotationResponse.model_validate(annotation)


@router.patch(
    "/{source_document_id}/annotations/{annotation_id}",
    response_model=AnnotationResponse,
)
async def update_annotation(
    source_document_id: UUID,
    annotation_id: UUID,
    body: AnnotationUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> AnnotationResponse:
    """Patch mutable fields (color, note) of an annotation.

    Returns 404 when the annotation does not belong to the given document.
    """
    existing = await repo.get_annotation(session, annotation_id)
    if existing is None or existing.source_document_id != source_document_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found")
    annotation = await repo.update_annotation(
        session,
        annotation_id,
        color=body.color,
        note=body.note,
    )
    return AnnotationResponse.model_validate(annotation)


@router.delete(
    "/{source_document_id}/annotations/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_annotation(
    source_document_id: UUID,
    annotation_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> None:
    """Delete an annotation. Returns 404 if it does not belong to the document."""
    annotation = await repo.get_annotation(session, annotation_id)
    if annotation is None or annotation.source_document_id != source_document_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found")
    await repo.delete_annotation(session, annotation_id)
