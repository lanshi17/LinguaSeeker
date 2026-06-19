"""Data types for document acquisition module."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .local_upload.contracts import LocalStoredFile
from .online_acquisition.contracts import OnlineAcquisitionItem, OnlineAcquisitionRouteInfo


class AcquisitionSource(str, Enum):
    """Document acquisition source type."""

    LOCAL = "local"
    ONLINE = "online"


@dataclass(frozen=True)
class DocumentDownloadEntry:
    """A single download result from online acquisition.

    ``pre_parsed_markdown`` is set when the acquisition pipeline already
    submitted the PDF to MinerU (multilingual workflow's early parse).
    Downstream Phase 1 can use it to skip MinerU re-parsing.
    """

    file_path: Optional[str] = None
    pdf_url: Optional[str] = None
    resolved_url: Optional[str] = None
    pre_parsed_markdown: Optional[str] = None

@dataclass
class DocumentAcquisitionRequest:
    """Unified request for document acquisition."""

    source: AcquisitionSource
    # local upload parameters
    filename: Optional[str] = None
    content: Optional[bytes] = None
    content_type: Optional[str] = None
    upload_dir: Optional[str] = None
    deduplicate: bool = False
    # online acquisition parameters
    action: Optional[str] = None
    query: Optional[str] = None
    identifiers: Optional[List[str]] = None
    limit: int = 20
    download_path: str = "./downloads"
    language: Optional[str] = "auto"
    prefer: str = "auto"
    api_provider: Optional[str] = None
    use_cache: bool = True
    max_retries: int = 3
    timeout: int = 60
    proxy: Optional[str] = None
    email: str = "[redacted-email]"


@dataclass
class DocumentAcquisitionResult:
    """Unified result for document acquisition."""

    success: bool
    source: AcquisitionSource
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None
    # local upload result fields
    stored_file: Optional[LocalStoredFile] = None
    deduplicated: bool = False
    # online acquisition result fields
    items: List[OnlineAcquisitionItem] = field(default_factory=list)
    downloads: List[DocumentDownloadEntry] = field(default_factory=list)
    route: Optional[OnlineAcquisitionRouteInfo] = None
    cached: bool = False
    # common fields
    elapsed_time: float = 0.0
    retries: int = 0
