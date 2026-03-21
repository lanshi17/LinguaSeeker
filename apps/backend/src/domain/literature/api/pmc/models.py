# src/domain/literature/api/pmc_http/schemas.py
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class PmcParams(BaseModel):
    # Search (ESearch)
    term: Optional[str] = None
    retmax: int = 20
    retstart: int = 0
    limit: Optional[int] = None
    max_pages: int = 10
    require_open_access: bool = True

    # Versions / metadata / download
    pmcid: Optional[str] = None
    pmcids: Optional[List[str]] = None
    version: Optional[int] = None

    # Download controls
    file_types: List[Literal["pdf", "xml", "txt", "media"]] = Field(
        default_factory=lambda: ["pdf"]
    )
    out_dir: str = "./pmc-downloads"
    download: bool = True
    download_concurrency: int = 3

    @field_validator("retmax", "max_pages", "download_concurrency")
    @classmethod
    def positive(cls, v: int):
        return max(1, v)

    @field_validator("retstart")
    @classmethod
    def non_negative(cls, v: int):
        return max(0, v)

    @field_validator("limit")
    @classmethod
    def limit_range(cls, v: Optional[int]):
        if v is None:
            return v
        return max(1, v)


class PmcPayload(BaseModel):
    action: Literal["search", "list_versions", "metadata", "download"] = "search"
    params: PmcParams

    esearch_base: str = "https://eutils.ncbi.nlm.nih.gov/eutils"
    s3_http_base: str = "https://pmc-oa-opendata.s3.amazonaws.com"

    timeout_s: float = 30
    max_retries: int = 2
    sleep_seconds: float = 0.5
    errors: Literal["raise", "ignore"] = "ignore"
    raw: bool = False
    user_agent: Optional[str] = None


class PmcMeta(BaseModel):
    count: Optional[int] = None
    retmax: Optional[int] = None
    retstart: Optional[int] = None
    term: Optional[str] = None
    pmcid: Optional[str] = None
    version: Optional[int] = None
    license_code: Optional[str] = None


class ApiResponse(BaseModel):
    success: bool
    items: List[Dict[str, Any]] = Field(default_factory=list)
    meta: Optional[PmcMeta] = None
    warnings: List[str] = Field(default_factory=list)
    raw: Optional[Any] = None
