"""Document parsing module for PDF to Markdown conversion.

Supports dual-engine parsing with automatic fallback:
- MinerU Local (primary): model-server VLM endpoint
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
from .mineru_local_parser import MinerULocalParser
from .service import ParseDocumentService

__all__ = [
    "DocumentMetadata",
    "FigurePosition",
    "MinerUAPIError",
    "MinerULocalParser",
    "MinerUTimeoutError",
    "PaddleOCRError",
    "PageContent",
    "ParseDocumentError",
    "ParseDocumentService",
    "ParseResult",
    "ParserExhaustedError",
    "TableStructure",
]
