"""Online acquisition module — layered architecture.

literature-io handles HTTP I/O, Python handles business logic.
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
from .doi_fallback import doi_fallback_download, probe_doi_landing_page
from .gateway import (
    call_provider,
    download_from_provider,
    search_provider,
)
from .normalizers import normalize_items
from .pubmed_service import OnlineAcquisitionPubMedArticle, OnlineAcquisitionPubMedCandidate, OnlineAcquisitionPubMedService, get_pubmed_service
from .search_service import build_provider_plan, search_multilingual
from .web_providers import call_web_provider
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
    "download_from_provider",
    # DOI fallback
    "probe_doi_landing_page",
    "doi_fallback_download",
    # PubMed
    "OnlineAcquisitionPubMedService",
    "OnlineAcquisitionPubMedCandidate",
    "OnlineAcquisitionPubMedArticle",
    "get_pubmed_service",
    # Web providers
    "call_web_provider",
    # Search
    "build_provider_plan",
    "search_multilingual",
    # Workflow
    "online_acquisition_workflow",
    # Normalizers
    "normalize_items",
]
