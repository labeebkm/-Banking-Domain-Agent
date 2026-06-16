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
CONNECT_TIMEOUT = 6    # seconds to establish TCP connection
READ_TIMEOUT = 15      # seconds to wait for response data
SNIPPET_LIMIT = 500
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Domain classification
# ---------------------------------------------------------------------------

# Official bank/regulator domains — used for citation priority and failed-URL
# preservation. These are NOT crawled directly for rate data because their
# rate pages are JavaScript-rendered and return empty shells to requests.
OFFICIAL_DOMAINS = (
    "rbi.org.in",
    "sbi.co.in",
    "hdfcbank.com",
    "icicibank.com",
    "axisbank.com",
    ".gov.in",
    ".nic.in",
)

# Aggregator domains — static HTML, crawlable, updated daily with bank rates.
# DuckDuckGo naturally returns pages from these domains for banking queries,
# so they are used here only for sort-priority, not for hardcoded URL paths.
AGGREGATOR_DOMAINS = (
    "bankbazaar.com",
    "paisabazaar.com",
    "groww.in",
    "myloancare.in",
    "cleartax.in",
    "deal4loans.com",
    "creditmantri.com",
    "wishfin.com",
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

# ---------------------------------------------------------------------------
# Tier 1 — Direct crawlable URLs (static HTML, verified working)
# ---------------------------------------------------------------------------

RBI_SOURCE_MAP: tuple[dict[str, Any], ...] = (
    {
        "keywords": (
            "rbi", "reserve bank", "repo rate", "monetary policy",
            "circular", "notification", "rbi announcement",
        ),
        "urls": (
            "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx",
            "https://www.rbi.org.in/Scripts/NotificationUser.aspx",
            "https://www.rbi.org.in/",
        ),
    },
)

# Groww aggregator URLs — verified static HTML, confirmed working.
# Scoped to FD queries only because Groww's loan pages returned 404.
# DuckDuckGo handles loan/other queries dynamically.
GROWW_SOURCE_MAP: tuple[dict[str, Any], ...] = (
    {
        "keywords": ("sbi fd", "sbi fixed deposit", "sbi deposit rate", "sbi recurring deposit"),
        "urls": ("https://groww.in/fixed-deposit/sbi-fd-interest-rates",),
    },
    {
        "keywords": ("hdfc fd", "hdfc fixed deposit", "hdfc deposit rate"),
        "urls": ("https://groww.in/fixed-deposit/hdfc-bank-fd-interest-rates",),
    },
    {
        "keywords": ("icici fd", "icici fixed deposit", "icici deposit rate"),
        "urls": ("https://groww.in/fixed-deposit/icici-bank-fd-interest-rates",),
    },
    {
        "keywords": ("axis fd", "axis fixed deposit", "axis deposit rate"),
        "urls": ("https://groww.in/fixed-deposit/axis-bank-fd-interest-rates",),
    },
)

HOME_LOAN_SOURCE_MAP: tuple[dict[str, Any], ...] = (
    {
        "keywords": ("sbi home loan", "state bank of india home loan", "sbi housing loan"),
        "urls": (
            "https://www.paisabazaar.com/home-loan/sbi-home-loan/",
            "https://www.bankbazaar.com/home-loan/sbi-home-loan-interest-rate.html",
            "https://homeloans.sbi/",
        ),
    },
    {
        "keywords": ("hdfc home loan", "hdfc housing loan"),
        "urls": (
            "https://www.paisabazaar.com/home-loan/hdfc-home-loan/",
            "https://www.bankbazaar.com/home-loan/hdfc-home-loan-interest-rate.html",
            "https://www.hdfcbank.com/personal/borrow/popular-loans/home-loan",
        ),
    },
    {
        "keywords": ("icici home loan", "icici bank home loan", "icici housing loan"),
        "urls": (
            "https://www.paisabazaar.com/home-loan/icici-home-loan/",
            "https://www.bankbazaar.com/home-loan/icici-home-loan-interest-rate.html",
            "https://www.icicibank.com/personal-banking/loans/home-loan",
        ),
    },
)

# ---------------------------------------------------------------------------
# Tier 3 — Bank official homepages (citation-only fallback)
# Appended only when Tiers 1 and 2 together produce fewer than MAX_CANDIDATE_URLS.
# These pages are JS-rendered and will not yield crawlable content, but they
# give the user an authoritative URL to visit and verify figures manually.
# ---------------------------------------------------------------------------
BANK_HOMEPAGE_MAP: tuple[dict[str, Any], ...] = (
    {"keywords": ("sbi", "state bank of india"), "url": "https://www.sbi.co.in/"},
    {"keywords": ("hdfc",),                       "url": "https://www.hdfcbank.com/"},
    {"keywords": ("icici",),                      "url": "https://www.icicibank.com/"},
    {"keywords": ("axis",),                       "url": "https://www.axisbank.com/"},
    {"keywords": ("rbi", "reserve bank"),         "url": "https://www.rbi.org.in/"},
)

# ---------------------------------------------------------------------------
# Query intent classification
# ---------------------------------------------------------------------------

_RATE_SIGNALS = (
    "rate", "interest", "fd", "fixed deposit", "deposit",
    "loan", "emi", "roi", "per annum",
)
_DOC_SIGNALS = (
    "document", "kyc", "eligib", "criteria", "required",
    "minimum balance", "open account", "account open",
)


def _query_intent(query: str) -> str:
    """Classify query intent: 'rate', 'document', or 'general'."""
    q = query.lower()
    if any(s in q for s in _DOC_SIGNALS):
        return "document"
    if any(s in q for s in _RATE_SIGNALS):
        return "rate"
    return "general"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _debug(message: str) -> None:
    if DEBUG_AGENTS:
        print(message)


def _clean_text(value: Any, limit: int = SNIPPET_LIMIT) -> str:
    """Collapse whitespace, strip non-ASCII, and truncate to limit."""
    text = unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text)
    text = text.encode("ascii", errors="ignore").decode("ascii").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rsplit(" ", 1)[0].strip() + "..."


def _clean_url(value: Any) -> str:
    """Normalize a URL and resolve DuckDuckGo redirect wrappers.

    www. is preserved in the returned URL so HTTP requests go to the correct
    hostname. Domain-matching helpers strip it internally for comparison.
    """
    raw_url = str(value or "").strip()
    if not raw_url:
        return ""

    parsed_raw = urlparse(raw_url)
    if "duckduckgo.com" in parsed_raw.netloc and parsed_raw.query:
        redirect_url = parse_qs(parsed_raw.query).get("uddg", [""])[0]
        if redirect_url:
            raw_url = unquote(redirect_url)

    parsed = urlparse(raw_url)
    if not parsed.scheme or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""

    hostname = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{hostname}{path}"


def _host(url: str) -> str:
    """Return the hostname without www. for domain matching."""
    hostname = urlparse(url).netloc.lower()
    return hostname[4:] if hostname.startswith("www.") else hostname


def _is_official_url(url: str) -> bool:
    h = _host(url)
    return any(h == d.lstrip(".") or h.endswith(d) for d in OFFICIAL_DOMAINS)


def _is_aggregator_url(url: str) -> bool:
    h = _host(url)
    return any(h == d or h.endswith(f".{d}") for d in AGGREGATOR_DOMAINS)


def _is_low_quality_url(url: str) -> bool:
    h = _host(url)
    return any(h == d or h.endswith(f".{d}") for d in LOW_QUALITY_DOMAINS)


def _query_terms(query: str) -> list[str]:
    stop_words = {
        "a", "an", "and", "are", "for", "from", "is", "latest",
        "of", "on", "the", "to", "what", "with", "give", "me", "tell",
    }
    terms = re.findall(r"[a-z0-9]+", query.lower())
    return [t for t in terms if len(t) > 2 and t not in stop_words]

# ---------------------------------------------------------------------------
# URL resolution
# ---------------------------------------------------------------------------

def _mapped_rbi_urls(query: str) -> list[str]:
    query_lower = query.lower()
    for source in RBI_SOURCE_MAP:
        if any(kw in query_lower for kw in source["keywords"]):
            return list(source["urls"])
    return []


def _mapped_groww_urls(query: str) -> list[str]:
    """Return Groww FD URLs for the matching product — verified static HTML."""
    query_lower = query.lower()
    for source in GROWW_SOURCE_MAP:
        if any(kw in query_lower for kw in source["keywords"]):
            return list(source["urls"])
    return []


def _mapped_home_loan_urls(query: str) -> list[str]:
    """Return crawlable home-loan rate URLs for known bank queries."""
    query_lower = query.lower()
    for source in HOME_LOAN_SOURCE_MAP:
        if any(kw in query_lower for kw in source["keywords"]):
            return list(source["urls"])
    return []


def _generic_homepage_urls(query: str) -> list[str]:
    query_lower = query.lower()
    return [
        entry["url"]
        for entry in BANK_HOMEPAGE_MAP
        if any(kw in query_lower for kw in entry["keywords"])
    ]


def _dedupe_urls(urls: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in urls:
        url = _clean_url(candidate)
        if not url or _is_low_quality_url(url):
            continue
        # Strip www. only for the dedup key so www.x.com and x.com are
        # treated as the same page, but the stored URL keeps www. for crawling.
        dedup_key = url.replace("://www.", "://", 1)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        unique.append(url)
    # Sort: official first, then aggregators, then everything else
    unique.sort(key=lambda u: 0 if _is_official_url(u) else 1 if _is_aggregator_url(u) else 2)
    return unique


def _resolve_duckduckgo_urls(query: str) -> list[str]:
    """Scrape DuckDuckGo HTML interface for result URLs."""
    search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    response = requests.get(
        search_url,
        headers={"User-Agent": USER_AGENT},
        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    urls: list[str] = []
    for anchor in soup.select("a.result__a, a.result__url"):
        href = anchor.get("href", "")
        if not href:
            continue
        if href.startswith("//"):
            href = f"https:{href}"
        elif href.startswith("/"):
            href = urljoin("https://html.duckduckgo.com", href)
        cleaned = _clean_url(href)
        if not cleaned or "duckduckgo.com" in cleaned:
            continue
        urls.append(cleaned)
        if len(urls) >= MAX_CANDIDATE_URLS:
            break
    return urls


def _get_with_retry(url: str) -> requests.Response:
    """Fetch a URL, retrying once on read timeout."""
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
    except requests.ReadTimeout:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
    response.raise_for_status()
    return response


def _candidate_urls(query: str) -> list[str]:
    """Build the crawl candidate list using a three-tier priority strategy.

    Tier 1 — RBI direct URLs: rbi.org.in is static HTML and never restructures,
              so hardcoded URLs are safe here. Only used for RBI-related queries.

    Tier 2 — DuckDuckGo: dynamically discovers the correct current aggregator
              URLs (BankBazaar, Groww, Paisabazaar etc.) for any bank/product
              query. This is the primary source for all bank rate queries because
              aggregator sites restructure their URLs periodically, making
              hardcoded paths fragile and unreliable.

    Tier 3 — Bank official homepages: citation-only fallback. These pages are
              JS-rendered and will not yield content, but preserve an official
              URL in the response for the user to verify figures manually.
    """
    candidates: list[str] = []

    # Tier 1 — RBI direct (stable government URLs)
    candidates.extend(_mapped_rbi_urls(query))

    # Tier 1b — Groww FD URLs (verified static HTML, scoped to FD queries only)
    for url in _mapped_groww_urls(query):
        if url not in candidates:
            candidates.append(url)

    # Tier 2 — DuckDuckGo dynamic discovery
    for url in _mapped_home_loan_urls(query):
        if url not in candidates:
            candidates.append(url)

    try:
        ddg_urls = _resolve_duckduckgo_urls(query)
        candidates.extend(url for url in ddg_urls if url not in candidates)
    except Exception as exc:
        _debug(f"DuckDuckGo resolver failed: {exc}")

    # Tier 3 — official bank homepages (citation fallback only)
    if len(candidates) < MAX_CANDIDATE_URLS:
        for url in _generic_homepage_urls(query):
            if url not in candidates:
                candidates.append(url)

    return _dedupe_urls(candidates)[:MAX_CANDIDATE_URLS]

# ---------------------------------------------------------------------------
# Page extraction
# ---------------------------------------------------------------------------

def _title_from_soup(soup: BeautifulSoup, url: str) -> str:
    if soup.title and soup.title.string:
        return _clean_text(soup.title.string, limit=90)
    heading = soup.find(["h1", "h2"])
    if heading:
        return _clean_text(heading.get_text(" "), limit=90)
    return _clean_text(_host(url) or "Official source", limit=90)


def _extract_page_lines(soup: BeautifulSoup) -> list[str]:
    lines: list[str] = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        json_text = _clean_text(script.get_text(" "), limit=800)
        for value in re.findall(r'"(?:name|description)"\s*:\s*"([^"]+)"', json_text):
            cleaned = _clean_text(value, limit=400)
            if len(cleaned) >= 8:
                lines.append(cleaned)

    for row in soup.find_all("tr", limit=120):
        cells = [
            _clean_text(cell.get_text(" "), limit=160)
            for cell in row.find_all(["th", "td"], recursive=False)
        ]
        cells = [cell for cell in cells if cell]
        if len(cells) >= 2:
            lines.append(" | ".join(cells))

    for element in soup(["script", "style", "noscript", "nav", "footer", "header", "svg"]):
        element.decompose()

    root = soup.find("main") or soup.find("article") or soup.body or soup
    for element in root.find_all(
        ["h1", "h2", "h3", "p", "li", "td", "th", "tr", "div", "span"], limit=420
    ):
        text = _clean_text(element.get_text(" "), limit=400)
        if len(text) < 8:
            continue
        lowered = text.lower()
        if any(marker in lowered for marker in (
            "cookie", "javascript", "enable js", "skip to", "privacy policy",
        )):
            continue
        lines.append(text)
    return lines


def _relevant_snippet(lines: list[str], query: str) -> str:
    """Score and select the most relevant lines from a crawled page."""
    if not lines:
        return ""

    query_lower = query.lower()
    combined_text = _clean_text(" ".join(lines), limit=6000)

    # Special case: extract the exact policy repo rate sentence for RBI queries
    if "repo" in query_lower:
        match = re.search(r"policy repo rate", combined_text, flags=re.IGNORECASE)
        if match:
            start = max(0, match.start() - 80)
            end = min(len(combined_text), match.end() + 220)
            return _clean_text(combined_text[start:end], limit=SNIPPET_LIMIT)

    terms = _query_terms(query)
    scored: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        line_lower = line.lower()
        score = sum(1 for term in terms if term in line_lower)
        if any(m in line_lower for m in (
            "rate", "interest", "repo", "charge", "fee", "rbi",
            "loan", "announc", "document", "eligib", "kyc",
        )):
            score += 1
        if "%" in line:
            score += 2  # strongest signal for rate data
        scored.append((score, -index, line))

    scored.sort(reverse=True)
    chosen = [line for s, _, line in scored if s > 0][:4] or lines[:4]
    return _clean_text(" ".join(chosen), limit=SNIPPET_LIMIT)


def _snippet_has_useful_content(snippet: str, query: str) -> bool:
    """Validate snippet quality based on query intent.

    rate     → must contain '%' or a numeric rate pattern
    document → must contain a document/eligibility keyword
    general  → any non-empty snippet accepted
    """
    if not snippet:
        return False

    intent = _query_intent(query)

    if intent == "rate":
        has_percent = "%" in snippet
        has_number = bool(re.search(
            r"\d+(?:\.\d+)?\s*(?:p\.a|per\s*annum|year|month|day|lakh|crore|years|months)",
            snippet, re.IGNORECASE,
        ))
        return has_percent or has_number

    if intent == "document":
        doc_keywords = (
            "aadhaar", "pan", "passport", "address proof", "identity",
            "photograph", "kyc", "document", "eligib", "income proof",
            "salary", "minimum", "balance",
        )
        return any(kw in snippet.lower() for kw in doc_keywords)

    return True


def _snippet_matches_query(snippet: str, query: str, title: str = "", url: str = "") -> bool:
    """Return True when a snippet appears relevant to the requested product."""
    haystack = f"{snippet} {title} {url}".lower()
    query_lower = query.lower()

    product_phrases = (
        "home loan",
        "personal loan",
        "car loan",
        "fixed deposit",
        "savings account",
        "credit card",
    )
    requested_products = [phrase for phrase in product_phrases if phrase in query_lower]
    if requested_products and not any(phrase in haystack for phrase in requested_products):
        return False

    bank_terms = ("sbi", "state bank", "hdfc", "icici", "axis")
    requested_banks = [term for term in bank_terms if term in query_lower]
    if requested_banks and not any(term in haystack for term in requested_banks):
        return False

    return _snippet_has_useful_content(snippet, query)

# ---------------------------------------------------------------------------
# Crawl a single page
# ---------------------------------------------------------------------------

def _crawl_page(url: str, query: str) -> dict[str, str] | None:
    try:
        response = _get_with_retry(url)
    except Exception as exc:
        _debug(f"Crawl failed for {url}: {exc}")
        return None

    content_type = response.headers.get("content-type", "")
    if (
        "text/html" not in content_type
        and "application/xhtml" not in content_type
        and not response.text.lstrip().startswith("<")
    ):
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    lines = _extract_page_lines(soup)
    snippet = _relevant_snippet(lines, query)

    title = _title_from_soup(soup, url)
    if not _snippet_matches_query(snippet, query, title, url):
        _debug(f"Skipping low-content snippet for {url}")
        return None

    return {
        "title":   title,
        "url":     _clean_url(url),
        "content": snippet,
    }

# ---------------------------------------------------------------------------
# Format results
# ---------------------------------------------------------------------------

def _format_search_results(
    results: list[dict[str, str]],
    failed_official_urls: list[str] | None = None,
) -> str:
    """Format crawled results into a compact block for the LLM summarizer.

    failed_official_urls contains official pages that were reached but returned
    JS-rendered or empty content. Appended as UNVERIFIED_OFFICIAL_URL lines so
    the LLM can cite them and direct the user to verify figures there directly.
    """
    failed_official_urls = failed_official_urls or []

    if not results and not failed_official_urls:
        return "No useful web search results were found."

    sections: list[str] = []

    for index, item in enumerate(results[:MAX_SEARCH_RESULTS], start=1):
        sections.append(
            f"{index}. {item['title']}\nURL: {item['url']}\nSnippet: {item['content']}"
        )

    for url in failed_official_urls[:3]:
        sections.append(f"UNVERIFIED_OFFICIAL_URL: {url}\nURL: {url}\nStatus: Unverified")

    return "\n\n".join(sections)

# ---------------------------------------------------------------------------
# LangChain tool
# ---------------------------------------------------------------------------

@tool
def web_search(query: str):
    """Crawl banking aggregator and official sources for live banking data,
    current loan rates, FD rates, latest RBI announcements, and banking
    information not available in local knowledge."""
    _debug("web_search crawler called")

    results: list[dict[str, str]] = []
    failed_official_urls: list[str] = []
    seen_urls: set[str] = set()

    for url in _candidate_urls(query):
        if url in seen_urls:
            continue
        seen_urls.add(url)

        crawled = _crawl_page(url, query)
        if crawled is not None:
            results.append(crawled)
        elif _is_official_url(url):
            # Official page reached but JS-rendered — preserve URL for citation
            clean = _clean_url(url)
            if clean:
                failed_official_urls.append(clean)

        if len(results) == MAX_SEARCH_RESULTS:
            break

    # Sort: official sources first, then aggregators, then everything else
    results.sort(key=lambda r: (
        0 if _is_official_url(r["url"]) else
        1 if _is_aggregator_url(r["url"]) else 2
    ))
    return _format_search_results(results, failed_official_urls)


WEB_SEARCH_TOOL = web_search
