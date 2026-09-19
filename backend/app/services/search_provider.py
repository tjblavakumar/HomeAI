from __future__ import annotations

import abc
from dataclasses import dataclass

import httpx

from app.config import settings


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str  # "tavily" | "duckduckgo"


class SearchProvider(abc.ABC):
    @abc.abstractmethod
    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        ...


class TavilyProvider(SearchProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        response = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": self.api_key, "query": query, "max_results": max_results},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        return [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                source="tavily",
            )
            for item in data.get("results", [])
        ]


class DuckDuckGoProvider(SearchProvider):
    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        from duckduckgo_search import DDGS  # unofficial, key-less, free fallback

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("href", ""),
                snippet=item.get("body", ""),
                source="duckduckgo",
            )
            for item in results
        ]


def get_search_provider() -> SearchProvider:
    """Use Tavily when TAVILY_API_KEY is set (checked at call time so the key
    can be added to .env later without restarting requiring a code change)."""
    if settings.tavily_api_key:
        return TavilyProvider(settings.tavily_api_key)
    return DuckDuckGoProvider()


def search_with_fallback(query: str, max_results: int = 5) -> list[SearchResult]:
    """Search with the configured provider, falling back to DuckDuckGo on any error."""
    provider = get_search_provider()
    try:
        results = provider.search(query, max_results=max_results)
        if results:
            return results
    except Exception:
        pass
    if not isinstance(provider, DuckDuckGoProvider):
        try:
            return DuckDuckGoProvider().search(query, max_results=max_results)
        except Exception:
            return []
    return []
