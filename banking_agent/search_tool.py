"""Local crawler-backed web-search tool for live banking information."""

from __future__ import annotations

import re
from html import unescape
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from banking_agent.config import DEBUG_AGENTS


MAX_SEARCH_RESULTS = 3
MAX_CANDIDATE_URLS = 8
REQUEST_TIMEOUT = 10
SNIPPET_LIMIT = 260
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36 BankingCrawler/1.0"
)

OFFICIAL_DOMAINS = (
    "rbi.org.in",
    "sbi.co.in",
    "sbi.bank.in",
    "hdfcbank.com",
    "icicibank.com",
    "axisbank.com",
    ".bank.in",
    ".gov.in",
    ".nic.in",
)
LOW_QUALITY_DOMAINS = (
    "quora.com",
    "reddit.com",
    "yahoo.com",
    "youtube.com",
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "pinterest.com",
)

OFFICIAL_SOURCE_MAP: tuple[dict[str, Any], ...] = (
    {
        "keywords": ("rbi", "reserve bank", "repo rate", "monetary policy", "circular", "notification", "announcement"),
        "urls": (
            "https://www.rbi.org.in/",
            "https://www.rbi.org.in/Scripts/NotificationUser.aspx",
            "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx",
            "https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx",
        ),
    },
    {
        "keywords": ("sbi", "state bank of india"),
        "urls": (
            "https://sbi.bank.in/web/interest-rates/interest-rates/loan-schemes-interest-rates/home-loans-interest-rates-current",
            "https://sbi.bank.in/web/interest-rates/interest-rates",
        ),
    },
    {
        "keywords": ("hdfc", "hdfc bank"),
        "urls": (
            "https://www.hdfcbank.com/personal/borrow/popular-loans/personal-loan",
            "https://www.hdfcbank.com/personal/resources/rates",
        ),
    },
    {
        "keywords": ("icici", "icici bank"),
        "urls": (
            "https://www.icicibank.com/personal-banking/cards/credit-card/fees-and-charges",
        ),
    },
    {
        "keywords": ("axis", "axis bank"),
        "urls": (
            "https://www.axisbank.com/retail/cards/credit-card/fees-and-charges",
            "https://www.axisbank.com/retail/loans/personal-loan/interest-rates-charges",
            "https://www.axisbank.com/interest-rate-on-deposits",
        ),
    },
)


def _debug(message: str) -> None:
    if DEBUG_AGENTS:
        print(message)


def _clean_text(value: Any, limit: int = SNIPPET_LIMIT) -> str:
    """Keep crawler text compact and safe for Windows console output."""
    text = unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text)
    text = text.encode("ascii", errors="ignore").decode("ascii").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rsplit(" ", 1)[0].strip() + "..."


def _clean_url(value: Any) -> str:
    """Normalize URLs enough to remove duplicates and DuckDuckGo redirects."""
    raw_url = str(value or "").strip()
    if not raw_url:
        return ""

    parsed_raw = urlparse(raw_url)
    if "duckduckgo.com" in parsed_raw.netloc and parsed_raw.query:
        redirect_url = parse_qs(parsed_raw.query).get("uddg", [""])[0]
        if redirect_url:
            raw_url = unquote(redirect_url)

    parsed = urlparse(raw_url)
    if not parsed.scheme:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""

    hostname = parsed.netloc.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{hostname}{path}"


def _is_official_url(url: str) -> bool:
    """Identify official bank, RBI, regulator, and government URLs."""
    hostname = urlparse(url).netloc.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return any(
        hostname == domain.lstrip(".") or hostname.endswith(domain)
        for domain in OFFICIAL_DOMAINS
    )


def _is_low_quality_url(url: str) -> bool:
    """Filter sources that are poor evidence for current banking rates."""
    hostname = urlparse(url).netloc.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in LOW_QUALITY_DOMAINS)


def _query_terms(query: str) -> list[str]:
    terms = re.findall(r"[a-z0-9]+", query.lower())
    stop_words = {
        "a",
        "an",
        "and",
        "are",
        "for",
        "from",
        "is",
        "latest",
        "of",
        "on",
        "the",
        "to",
        "what",
        "with",
    }
    return [term for term in terms if len(term) > 2 and term not in stop_words]


def _mapped_source_urls(query: str) -> list[str]:
    query_lower = query.lower()
    urls: list[str] = []
    for source in OFFICIAL_SOURCE_MAP:
        if any(keyword in query_lower for keyword in source["keywords"]):
            urls.extend(source["urls"])
    return urls


def _mapped_source_domains(query: str) -> set[str]:
    query_lower = query.lower()
    domains: set[str] = set()
    for source in OFFICIAL_SOURCE_MAP:
        if not any(keyword in query_lower for keyword in source["keywords"]):
            continue
        for url in source["urls"]:
            hostname = urlparse(url).netloc.lower()
            if hostname.startswith("www."):
                hostname = hostname[4:]
            domains.add(hostname)
    return domains


def _matches_allowed_domains(url: str, allowed_domains: set[str]) -> bool:
    if not allowed_domains:
        return True
    hostname = urlparse(url).netloc.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed_domains)


def _dedupe_urls(urls: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in urls:
        url = _clean_url(candidate)
        if not url or url in seen or _is_low_quality_url(url):
            continue
        seen.add(url)
        unique.append(url)
    unique.sort(key=lambda item: 0 if _is_official_url(item) else 1)
    return unique


def _resolve_duckduckgo_urls(query: str) -> list[str]:
    search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    response = requests.get(search_url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    urls: list[str] = []
    for anchor in soup.select("a.result__a, a.result__url, a[href]"):
        href = anchor.get("href")
        if not href:
            continue
        if href.startswith("//"):
            href = f"https:{href}"
        elif href.startswith("/"):
            href = urljoin("https://html.duckduckgo.com", href)
        cleaned = _clean_url(href)
        if cleaned:
            urls.append(cleaned)
        if len(urls) >= MAX_CANDIDATE_URLS:
            break
    return urls


def _candidate_urls(query: str) -> list[str]:
    mapped_urls = _mapped_source_urls(query)
    mapped_domains = _mapped_source_domains(query)
    candidates = list(mapped_urls)
    if len(candidates) < MAX_CANDIDATE_URLS:
        try:
            candidates.extend(
                url for url in _resolve_duckduckgo_urls(query) if _matches_allowed_domains(url, mapped_domains)
            )
        except Exception as exc:
            _debug(f"DuckDuckGo resolver failed: {exc}")
    return _dedupe_urls(candidates)[:MAX_CANDIDATE_URLS]


def _title_from_soup(soup: BeautifulSoup, url: str) -> str:
    if soup.title and soup.title.string:
        return _clean_text(soup.title.string, limit=90)
    heading = soup.find(["h1", "h2"])
    if heading:
        return _clean_text(heading.get_text(" "), limit=90)
    return _clean_text(urlparse(url).netloc or "Official source", limit=90)


def _extract_page_lines(soup: BeautifulSoup) -> list[str]:
    for element in soup(["script", "style", "noscript", "nav", "footer", "header", "svg"]):
        element.decompose()

    root = soup.find("main") or soup.find("article") or soup.body or soup
    lines: list[str] = []
    for element in root.find_all(["h1", "h2", "h3", "p", "li", "td", "th", "tr", "div", "span"], limit=420):
        text = _clean_text(element.get_text(" "), limit=400)
        if len(text) < 8:
            continue
        lowered = text.lower()
        if any(marker in lowered for marker in ("cookie", "javascript", "enable js", "skip to", "privacy policy")):
            continue
        lines.append(text)
    return lines


def _relevant_snippet(lines: list[str], query: str) -> str:
    terms = _query_terms(query)
    if not lines:
        return ""

    query_lower = query.lower()
    combined_text = _clean_text(" ".join(lines), limit=6000)
    if "repo" in query_lower:
        repo_match = re.search(r"policy repo rate", combined_text, flags=re.IGNORECASE)
        if repo_match:
            start = max(0, repo_match.start() - 80)
            end = min(len(combined_text), repo_match.end() + 220)
            return _clean_text(combined_text[start:end], limit=SNIPPET_LIMIT)

    scored_lines: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        line_lower = line.lower()
        score = sum(1 for term in terms if term in line_lower)
        if any(marker in line_lower for marker in ("rate", "interest", "repo", "charge", "fee", "rbi", "loan", "announc")):
            score += 1
        scored_lines.append((score, -index, line))

    scored_lines.sort(reverse=True)
    chosen = [line for score, _index, line in scored_lines if score > 0][:2]
    if not chosen:
        chosen = lines[:2]
    return _clean_text(" ".join(chosen), limit=SNIPPET_LIMIT)


def _crawl_page(url: str, query: str) -> dict[str, str] | None:
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except Exception as exc:
        _debug(f"Crawl failed for {url}: {exc}")
        return None

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type and not response.text.lstrip().startswith("<"):
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    lines = _extract_page_lines(soup)
    snippet = _relevant_snippet(lines, query)
    if not snippet:
        return None

    return {
        "title": _title_from_soup(soup, url),
        "url": _clean_url(url),
        "content": snippet,
    }


def _format_search_results(results: list[dict[str, str]]) -> str:
    if not results:
        return "No useful web search results were found."

    formatted_results: list[str] = []
    for index, item in enumerate(results[:MAX_SEARCH_RESULTS], start=1):
        formatted_results.append(
            f"{index}. {item['title']}\nURL: {item['url']}\nSnippet: {item['content']}"
        )
    return "\n\n".join(formatted_results)


@tool
def web_search(query: str):
    """Crawl official banking sources for live banking data, current loan rates, latest RBI announcements, recent financial news, or banking information not available in local knowledge."""
    _debug("web_search crawler called")

    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for url in _candidate_urls(query):
        if url in seen_urls:
            continue
        seen_urls.add(url)
        crawled = _crawl_page(url, query)
        if crawled is not None:
            results.append(crawled)
        if len(results) == MAX_SEARCH_RESULTS:
            break

    results.sort(key=lambda item: 0 if _is_official_url(item["url"]) else 1)
    return _format_search_results(results)


WEB_SEARCH_TOOL = web_search
