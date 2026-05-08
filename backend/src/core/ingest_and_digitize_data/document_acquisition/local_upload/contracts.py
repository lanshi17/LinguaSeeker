"""Data types for local file upload."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# Allowed file extensions
ALLOWED_EXTENSIONS = frozenset({".pdf", ".doc", ".docx"})

# Max file size: 50MB
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class LocalUploadedFile:
    """Represents a validated uploaded file."""
    filename: str
    content: bytes
    content_type: Optional[str] = None
    size: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "size", len(self.content))


@dataclass(frozen=True)
class LocalStoredFile:
    """Result of storing a file to disk."""
    file_path: str
    sha256: str
    original_filename: str
    size: int
    content_type: Optional[str] = None


@dataclass
class LocalUploadResult:
    """Final upload result returned to caller."""
    success: bool
    stored_file: Optional[LocalStoredFile] = None
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None
