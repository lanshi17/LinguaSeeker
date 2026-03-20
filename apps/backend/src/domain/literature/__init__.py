from src.domain.literature.acquisition_agent import (
    LiteratureAcquisitionAgent,
    get_literature_acquisition_agent,
)
from src.domain.literature.unified import (
    UnifiedLiteratureRequest,
    UnifiedLiteratureResponse,
    literature_unified_workflow,
)

__all__ = [
    "LiteratureAcquisitionAgent",
    "UnifiedLiteratureRequest",
    "UnifiedLiteratureResponse",
    "get_literature_acquisition_agent",
    "literature_unified_workflow",
]

# Optional compatibility exports for legacy modules.
try:
    from src.domain.literature.firecrawl_service import (  # type: ignore
        FirecrawlMarkdownResult,
        FirecrawlService,
        get_firecrawl_service,
    )

    __all__.extend(
        [
            "FirecrawlMarkdownResult",
            "FirecrawlService",
            "get_firecrawl_service",
        ]
    )
except Exception:
    pass

try:
    from src.domain.literature.pubmed_service import (  # type: ignore
        PubMedArticle,
        PubMedCandidate,
        PubMedService,
        get_pubmed_service,
    )

    __all__.extend(
        [
            "PubMedArticle",
            "PubMedCandidate",
            "PubMedService",
            "get_pubmed_service",
        ]
    )
except Exception:
    pass
