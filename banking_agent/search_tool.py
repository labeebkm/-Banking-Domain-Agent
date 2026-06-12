"""Tavily web-search tool for live banking information."""

from typing import Any
from urllib.parse import urlparse

from langchain_tavily import TavilySearch
from langchain_core.tools import tool

from banking_agent.config import DEBUG_AGENTS, TAVILY_API_KEY


MAX_SEARCH_RESULTS = 3
SNIPPET_LIMIT = 220
OFFICIAL_DOMAINS = (
    "rbi.org.in",
    "sbi.bank.in",
    ".bank.in",
    ".gov.in",
    ".nic.in",
)
LOW_QUALITY_DOMAINS = (
    "quora.com",
    "reddit.com",
    "yahoo.com",
    "youtube.com",
)


def _clean_text(value: Any) -> str:
    """Keep live-search text safe for Windows console output."""
    text = str(value)
    clean = " ".join(text.encode("ascii", errors="ignore").decode("ascii").split())
    return clean[:SNIPPET_LIMIT]


def _clean_url(value: Any) -> str:
    """Normalize URLs enough to remove duplicates from search results."""
    url = str(value or "").strip()
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    path = parsed.path.rstrip("/").lower()
    hostname = parsed.netloc.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return f"{parsed.scheme}://{hostname}{path}"


def _is_official_url(url: str) -> bool:
    """Identify official bank, RBI, regulator, and government URLs."""
    hostname = urlparse(url).netloc.lower()
    return any(hostname == domain or hostname.endswith(domain) for domain in OFFICIAL_DOMAINS)


def _is_low_quality_url(url: str) -> bool:
    """Filter sources that are poor evidence for current banking rates."""
    hostname = urlparse(url).netloc.lower()
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in LOW_QUALITY_DOMAINS)


def _build_search_query(query: str) -> str:
    """Pass through the Search Agent's rewritten query."""
    return query


def _format_search_results(result: Any, preferred_sources: list[dict[str, str]] | None = None) -> str:
    """Return up to three compact, deduplicated search results."""
    if not isinstance(result, dict):
        return str(result)

    results = [*(preferred_sources or []), *(result.get("results") or [])]
    if not results:
        return "No useful web search results were found."

    unique_results: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            continue

        url = _clean_url(item.get("url"))
        if not url or url in seen_urls:
            continue
        if _is_low_quality_url(url):
            continue

        seen_urls.add(url)
        unique_results.append(
            {
                "title": _clean_text(item.get("title") or "Untitled result"),
                "url": url,
                "content": _clean_text(item.get("content") or "No snippet available."),
            }
        )

    unique_results.sort(key=lambda item: 0 if _is_official_url(item["url"]) else 1)
    unique_results = unique_results[:MAX_SEARCH_RESULTS]

    formatted_results = [
        "Use these compact web search results as sources. Prefer official URLs and cite at most 3 URLs."
    ]
    for index, item in enumerate(unique_results, start=1):
        formatted_results.append(
            f"{index}. {item['title']}\nURL: {item['url']}\nSnippet: {item['content']}"
        )

    return "\n\n".join(formatted_results)


@tool
def web_search(query: str):
    """Search the internet for live banking data, current loan rates, latest RBI announcements, recent financial news, or banking information not available in local knowledge. Prefer official sources and include dates when results are time-sensitive."""
    if DEBUG_AGENTS:
        print("web_search called")

    search = TavilySearch(max_results=MAX_SEARCH_RESULTS, tavily_api_key=TAVILY_API_KEY)
    try:
        search_results = _format_search_results(
            search.invoke({"query": _build_search_query(query)}),
        )
    except Exception as exc:
        return (
            "Live search is unavailable right now. Please verify current banking "
            "details with the latest official bank or regulator source. "
            f"Details: {exc}"
        )
    return search_results


WEB_SEARCH_TOOL = web_search
