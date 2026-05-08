"""Document acquisition module — unified interface for local upload and online acquisition."""

from .service import DocumentAcquisitionService
from .contracts import (
    AcquisitionSource,
    DocumentAcquisitionRequest,
    DocumentAcquisitionResult,
    DocumentDownloadEntry,
)

__all__ = [
    "DocumentAcquisitionService",
    "DocumentAcquisitionRequest",
    "DocumentAcquisitionResult",
    "AcquisitionSource",
]
