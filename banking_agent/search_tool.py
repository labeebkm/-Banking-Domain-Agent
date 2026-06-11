"""Tavily web-search tool for live banking information."""

from typing import Any

from langchain_tavily import TavilySearch
from langchain_core.tools import tool

from banking_agent.config import TAVILY_API_KEY


def _clean_text(value: Any) -> str:
    """Keep live-search text safe for Windows console output."""
    text = str(value)
    return text.encode("ascii", errors="ignore").decode("ascii")


def _build_search_query(query: str) -> str:
    """Add official-source hints for time-sensitive banking searches."""
    query_lower = query.lower()
    if "sbi" in query_lower or "state bank of india" in query_lower:
        return f"{query} SBI official latest home loan interest rates India"
    return f"{query} official source"


def _format_search_results(result: Any) -> str:
    """Return search results in a citation-friendly format for the agent."""
    if not isinstance(result, dict):
        return str(result)

    results = result.get("results") or []
    if not results:
        return "No useful web search results were found."

    formatted_results = [
        "Use these web search results as sources. Prefer official bank or regulator pages over third-party aggregators, and cite URLs in the final answer."
    ]
    for index, item in enumerate(results, start=1):
        if not isinstance(item, dict):
            continue

        title = _clean_text(item.get("title") or "Untitled result")
        url = _clean_text(item.get("url") or "No URL")
        content = _clean_text(item.get("content") or "No snippet available.")
        formatted_results.append(
            f"{index}. {title}\nURL: {url}\nSnippet: {content}"
        )

    return "\n\n".join(formatted_results)


def _preferred_official_sources(query: str) -> str:
    """Provide known official pages for common bank-rate queries."""
    query_lower = query.lower()
    if (
        ("sbi" in query_lower or "state bank of india" in query_lower)
        and "home" in query_lower
        and "loan" in query_lower
    ):
        return (
            "Preferred official source for SBI home-loan rates:\n"
            "SBI Home Loans Interest Rates (Current)\n"
            "URL: https://sbi.bank.in/web/interest-rates/interest-rates/loan-schemes-interest-rates/home-loans-interest-rates-current"
        )
    return ""


@tool
def web_search(query: str):
    """Search the internet for live banking data, current loan rates, latest RBI announcements, recent financial news, or banking information not available in local knowledge. Prefer official sources and include dates when results are time-sensitive."""
    search = TavilySearch(max_results=5, tavily_api_key=TAVILY_API_KEY)
    preferred_sources = _preferred_official_sources(query)
    try:
        search_results = _format_search_results(
            search.invoke({"query": _build_search_query(query)})
        )
    except Exception as exc:
        return (
            "Live search is unavailable right now. Please verify current banking "
            "details with the latest official bank or regulator source. "
            f"Details: {exc}"
        )
    if preferred_sources:
        return f"{preferred_sources}\n\n{search_results}"
    return search_results


WEB_SEARCH_TOOL = web_search
