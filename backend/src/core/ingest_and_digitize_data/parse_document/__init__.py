"""Document parsing module for PDF to Markdown conversion.

Supports dual-engine parsing with automatic fallback:
- MinerU (primary): HTTP API remote service
- PaddleOCR (fallback): Locally deployed model
"""

from .contracts import (
    DocumentMetadata,
    FigurePosition,
    PageContent,
    ParseResult,
    TableStructure,
)
from .exceptions import (
    MinerUAPIError,
    MinerUTimeoutError,
    PaddleOCRError,
    ParseDocumentError,
    ParserExhaustedError,
)
from .service import ParseDocumentService

__all__ = [
    "DocumentMetadata",
    "FigurePosition",
    "MinerUAPIError",
    "MinerUTimeoutError",
    "PaddleOCRError",
    "PageContent",
    "ParseDocumentError",
    "ParseDocumentService",
    "ParseResult",
    "ParserExhaustedError",
    "TableStructure",
]
