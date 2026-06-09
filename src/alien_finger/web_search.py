from __future__ import annotations

import os
import re
from dataclasses import dataclass
from html import unescape
from typing import Protocol

import httpx


class WebSearchError(RuntimeError):
    pass


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class SearchBackend(Protocol):
    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        ...


class SerperSearch:
    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        api_key = os.environ.get("SERPER_API_KEY")
        if not api_key:
            raise WebSearchError("SERPER_API_KEY is not set")
        response = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": limit},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return [
            SearchResult(item.get("title", ""), item.get("link", ""), item.get("snippet", ""))
            for item in data.get("organic", [])[:limit]
        ]


class TavilySearch:
    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            raise WebSearchError("TAVILY_API_KEY is not set")
        response = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": query, "max_results": limit},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return [
            SearchResult(item.get("title", ""), item.get("url", ""), item.get("content", ""))
            for item in data.get("results", [])[:limit]
        ]


class DuckDuckGoSearch:
    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        response = httpx.get("https://duckduckgo.com/html/", params={"q": query}, timeout=30)
        response.raise_for_status()
        html = response.text
        results: list[SearchResult] = []
        for match in re.finditer(
            r'<a rel="nofollow" class="result__a" href="(?P<url>.*?)".*?>(?P<title>.*?)</a>.*?<a class="result__snippet".*?>(?P<snippet>.*?)</a>',
            html,
            re.DOTALL,
        ):
            title = _clean_html(match.group("title"))
            url = unescape(match.group("url"))
            snippet = _clean_html(match.group("snippet"))
            results.append(SearchResult(title, url, snippet))
            if len(results) >= limit:
                break
        return results


def build_search_backend(name: str | None) -> SearchBackend:
    if name == "serper":
        return SerperSearch()
    if name == "tavily":
        return TavilySearch()
    if name == "duckduckgo":
        return DuckDuckGoSearch()
    raise WebSearchError("Web search backend is not configured")


def format_results(results: list[SearchResult]) -> str:
    if not results:
        return "No results."
    lines: list[str] = []
    for index, result in enumerate(results, start=1):
        lines.append(f"{index}. {result.title}\nURL: {result.url}\nSnippet: {result.snippet}")
    return "\n\n".join(lines)


def _clean_html(value: str) -> str:
    value = re.sub(r"<.*?>", "", value)
    return unescape(value).strip()
