from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QdrantHealthResponseDto(BaseModel):
	"""Qdrant health check response."""

	status: str = Field(..., description="Service status, usually 'ok' or 'error'.")
	details: Optional[Dict[str, Any]] = Field(None, description="Extra health details.")


class QdrantCollectionInfoDto(BaseModel):
	"""Qdrant collection info response."""

	name: str = Field(..., description="Collection name.")
	vectors_count: int = Field(..., description="Vector count.")
	segments_count: int = Field(..., description="Segment count.")
	index_status: str = Field(..., description="Index status.")
	storage_size: Optional[int] = Field(None, description="Storage size in bytes.")
	config: Optional[Dict[str, Any]] = Field(None, description="Collection config.")


class QdrantPointDto(BaseModel):
	"""Qdrant point payload."""

	id: str = Field(..., description="Point ID.")
	vector: List[float] = Field(..., description="Vector data.")
	payload: Optional[Dict[str, Any]] = Field(None, description="Point payload.")


class QdrantSearchResultItemDto(BaseModel):
	"""Qdrant search result item."""

	point_id: str = Field(..., description="Point ID.")
	score: float = Field(..., description="Similarity score.")
	payload: Optional[Dict[str, Any]] = Field(None, description="Point payload.")


class QdrantSearchResponseDto(BaseModel):
	"""Qdrant search response."""

	results: List[QdrantSearchResultItemDto] = Field(
		..., description="Search result items."
	)
