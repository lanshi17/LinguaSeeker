# src/domain/literature/api/unpaywall_http/schemas.py
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class SearchParams(BaseModel):
    keyword: List[str] = Field(default_factory=list)
    query: Optional[str] = None
    filters: Dict[str, Any] = Field(default_factory=dict)  # supports: is_oa
    limit: int = 50
    page: int = 1

    @field_validator("limit")
    @classmethod
    def limit_range(cls, v: int):
        return max(1, min(v, 500))

    @field_validator("page")
    @classmethod
    def page_min(cls, v: int):
        return max(1, v)


class UnpaywallPayload(BaseModel):
    action: Literal["query", "doi", "download"] = "query"

    # auth
    email: Optional[str] = None

    # query
    search_params: Optional[SearchParams] = None

    # doi query
    doi_list: List[str] = Field(default_factory=list)
    doi: Optional[str] = None

    # download
    selected_index: int = 0
    download_path: str = "./downloads"

    # runtime
    base_url: str = "https://api.unpaywall.org/v2"
    timeout_s: float = 30
    max_retries: int = 2
    sleep_seconds: float = 1.0
    progress: bool = False
    errors: Literal["raise", "ignore"] = "ignore"
    raw: bool = False
    user_agent: Optional[str] = None


class ApiResponse(BaseModel):
    success: bool
    items: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    raw: Optional[Any] = None


class DownloadResponse(BaseModel):
    success: bool
    pdf_url: Optional[str] = None
    doc_url: Optional[str] = None
    file_path: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
