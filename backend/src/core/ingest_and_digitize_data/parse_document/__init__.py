"""Document parsing module — MinerU VLM engine."""

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
    ParseDocumentError,
    ParserExhaustedError,
)
from .local.parser import MinerULocalParser
from .remote.parser import MinerURemoteParser
from .service import ParseDocumentService

__all__ = [
    "DocumentMetadata",
    "FigurePosition",
    "MinerUAPIError",
    "MinerULocalParser",
    "MinerURemoteParser",
    "MinerUTimeoutError",
    "PageContent",
    "ParseDocumentError",
    "ParseDocumentService",
    "ParseResult",
    "ParserExhaustedError",
    "TableStructure",
]
