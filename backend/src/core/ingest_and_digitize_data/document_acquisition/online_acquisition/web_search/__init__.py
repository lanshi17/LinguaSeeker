"""Web search adapter package — adapter pattern for pluggable search backends."""

from .adapter import SearchLink, WebSearchAdapter, WebSearchResult
from .tavily_adapter import TavilyAdapter

__all__ = ["SearchLink", "WebSearchAdapter", "WebSearchResult", "TavilyAdapter"]
