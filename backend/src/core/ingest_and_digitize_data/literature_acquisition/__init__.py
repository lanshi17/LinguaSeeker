"""Literature acquisition module — layered architecture.

rust-io handles HTTP I/O, Python handles business logic.
"""

from .contracts import (
    GatewayRequest,
    GatewayResult,
    LiteratureItem,
    LiteratureRequest,
    LiteratureResponse,
    RouteInfo,
    SourceTraceEntry,
)
from .doi_fallback import doi_fallback_download, probe_doi_landing_page
from .gateway import (
    call_provider,
    download_from_provider,
    search_provider,
)
from .normalizers import normalize_items
from .pubmed_service import PubMedArticle, PubMedCandidate, PubMedService, get_pubmed_service
from .search_service import build_provider_plan, search_multilingual
from .web_providers import WebGatewayRequest, call_web_provider
from .workflow import literature_workflow

__all__ = [
    # Contracts
    "LiteratureItem",
    "LiteratureRequest",
    "LiteratureResponse",
    "RouteInfo",
    "GatewayRequest",
    "GatewayResult",
    "SourceTraceEntry",
    # Gateway
    "call_provider",
    "search_provider",
    "download_from_provider",
    # DOI fallback
    "probe_doi_landing_page",
    "doi_fallback_download",
    # PubMed
    "PubMedService",
    "PubMedCandidate",
    "PubMedArticle",
    "get_pubmed_service",
    # Web providers
    "WebGatewayRequest",
    "call_web_provider",
    # Search
    "build_provider_plan",
    "search_multilingual",
    # Workflow
    "literature_workflow",
    # Normalizers
    "normalize_items",
]
