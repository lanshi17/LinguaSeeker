"""Web search adapter package — adapter pattern for pluggable search backends."""

from .adapter import SearchLink, WebSearchAdapter, WebSearchResult

__all__ = ["SearchLink", "WebSearchAdapter", "WebSearchResult"]
