"""Data types for document acquisition module."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AcquisitionSource(str, Enum):
    """Document acquisition source type."""

    LOCAL = "local"
    ONLINE = "online"


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
    web_provider: Optional[str] = None
    api_provider: Optional[str] = None
    use_cache: bool = True
    max_retries: int = 3
    timeout: int = 60
    proxy: Optional[str] = None
    email: str = "yhvguk@stu.hunau.edu.cn"


@dataclass
class DocumentAcquisitionResult:
    """Unified result for document acquisition."""

    success: bool
    source: AcquisitionSource
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None
    # local upload result fields
    stored_file: Optional[Any] = None  # LocalStoredFile
    deduplicated: bool = False
    # online acquisition result fields
    items: List[Any] = field(default_factory=list)  # List[OnlineAcquisitionItem]
    downloads: List[Dict[str, Any]] = field(default_factory=list)
    route: Optional[Any] = None  # RouteInfo
    cached: bool = False
    # common fields
    elapsed_time: float = 0.0
    retries: int = 0
