"""Online acquisition module — layered architecture.

net-io handles HTTP I/O, Python handles business logic.
"""

from .contracts import (
    OnlineAcquisitionGatewayRequest,
    OnlineAcquisitionGatewayResult,
    OnlineAcquisitionItem,
    OnlineAcquisitionRequest,
    OnlineAcquisitionResponse,
    OnlineAcquisitionRouteInfo,
    OnlineAcquisitionSourceTraceEntry,
)
from .gateway import (
    call_provider,
    search_provider,
)
from .normalizers import normalize_items
from .pubmed_service import OnlineAcquisitionPubMedArticle, OnlineAcquisitionPubMedCandidate, OnlineAcquisitionPubMedService, get_pubmed_service
from .search_service import build_provider_plan, search_multilingual
from .workflow import online_acquisition_workflow

__all__ = [
    # Contracts
    "OnlineAcquisitionItem",
    "OnlineAcquisitionRequest",
    "OnlineAcquisitionResponse",
    "OnlineAcquisitionRouteInfo",
    "OnlineAcquisitionGatewayRequest",
    "OnlineAcquisitionGatewayResult",
    "OnlineAcquisitionSourceTraceEntry",
    # Gateway
    "call_provider",
    "search_provider",
    # PubMed
    "OnlineAcquisitionPubMedService",
    "OnlineAcquisitionPubMedCandidate",
    "OnlineAcquisitionPubMedArticle",
    "get_pubmed_service",
    # Web providers
    # Search
    "build_provider_plan",
    "search_multilingual",
    # Workflow
    "online_acquisition_workflow",
    # Normalizers
    "normalize_items",
]
