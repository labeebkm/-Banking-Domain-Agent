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
CONNECT_TIMEOUT = 6   # seconds to establish TCP connection
READ_TIMEOUT = 15     # seconds to wait for response data
SNIPPET_LIMIT = 500
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# Domains treated as authoritative official sources (used for citation priority).
# Bank websites are listed here for citation purposes only — they are NOT crawled
# directly because their rate pages are JavaScript-rendered and return empty shells.
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
# Tier 1a — RBI direct URLs (static HTML, always crawlable)
# ---------------------------------------------------------------------------
RBI_SOURCE_MAP: tuple[dict[str, Any], ...] = (
    {
        "keywords": ("rbi", "reserve bank", "repo rate", "monetary policy", "circular", "notification", "rbi announcement"),
        "urls": (
            "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx",
            "https://www.rbi.org.in/Scripts/NotificationUser.aspx",
            "https://www.rbi.org.in/",
        ),
    },
)

# ---------------------------------------------------------------------------
# Tier 1b — Aggregator URLs per bank + product (static HTML, rate tables visible)
# Bank websites are intentionally excluded here — they are JS-rendered and
# return empty shells to requests. Aggregators serve the same data in plain HTML.
# ---------------------------------------------------------------------------
AGGREGATOR_SOURCE_MAP: tuple[dict[str, Any], ...] = (
    # SBI — home loan
    {
        "keywords": ("sbi home loan", "state bank home loan", "sbi housing loan"),
        "urls": (
            "https://www.bankbazaar.com/home-loan/sbi-home-loan-interest-rate.html",
            "https://www.paisabazaar.com/home-loan/sbi-home-loan-interest-rate/",
            "https://groww.in/p/loans/sbi-home-loan",
        ),
    },
    # SBI — personal loan
    {
        "keywords": ("sbi personal loan",),
        "urls": (
            "https://www.bankbazaar.com/personal-loan/sbi-personal-loan-interest-rate.html",
            "https://www.paisabazaar.com/personal-loan/sbi-personal-loan/",
        ),
    },
    # SBI — fixed deposit
    {
        "keywords": ("sbi fd", "sbi fixed deposit", "sbi rd", "sbi recurring deposit", "sbi deposit rate"),
        "urls": (
            "https://www.bankbazaar.com/fixed-deposit/sbi-fd-rates.html",
            "https://groww.in/fixed-deposit/sbi-fd-interest-rates",
            "https://www.paisabazaar.com/fixed-deposit/sbi-fixed-deposit-interest-rates/",
        ),
    },
    # SBI — savings account / documents / eligibility
    {
        "keywords": ("sbi savings account", "sbi account open", "sbi kyc", "sbi document", "sbi eligib", "sbi minimum balance"),
        "urls": (
            "https://www.bankbazaar.com/savings-account/sbi-savings-account.html",
            "https://www.myloancare.in/savings-account/sbi-savings-account/",
        ),
    },
    # HDFC — home loan
    {
        "keywords": ("hdfc home loan", "hdfc housing loan"),
        "urls": (
            "https://www.bankbazaar.com/home-loan/hdfc-home-loan-interest-rate.html",
            "https://www.paisabazaar.com/home-loan/hdfc-home-loan-interest-rate/",
            "https://groww.in/p/loans/hdfc-home-loan",
        ),
    },
    # HDFC — personal loan
    {
        "keywords": ("hdfc personal loan",),
        "urls": (
            "https://www.bankbazaar.com/personal-loan/hdfc-personal-loan-interest-rate.html",
            "https://www.paisabazaar.com/personal-loan/hdfc-personal-loan/",
        ),
    },
    # HDFC — fixed deposit
    {
        "keywords": ("hdfc fd", "hdfc fixed deposit", "hdfc deposit rate"),
        "urls": (
            "https://www.bankbazaar.com/fixed-deposit/hdfc-bank-fd-rates.html",
            "https://groww.in/fixed-deposit/hdfc-bank-fd-interest-rates",
            "https://www.paisabazaar.com/fixed-deposit/hdfc-bank-fd-interest-rates/",
        ),
    },
    # ICICI — home loan
    {
        "keywords": ("icici home loan", "icici housing loan"),
        "urls": (
            "https://www.bankbazaar.com/home-loan/icici-home-loan-interest-rate.html",
            "https://www.paisabazaar.com/home-loan/icici-home-loan-interest-rate/",
            "https://groww.in/p/loans/icici-bank-home-loan",
        ),
    },
    # ICICI — personal loan
    {
        "keywords": ("icici personal loan",),
        "urls": (
            "https://www.bankbazaar.com/personal-loan/icici-personal-loan-interest-rate.html",
            "https://www.paisabazaar.com/personal-loan/icici-personal-loan/",
        ),
    },
    # ICICI — fixed deposit
    {
        "keywords": ("icici fd", "icici fixed deposit", "icici deposit rate"),
        "urls": (
            "https://www.bankbazaar.com/fixed-deposit/icici-bank-fd-rates.html",
            "https://groww.in/fixed-deposit/icici-bank-fd-interest-rates",
            "https://www.paisabazaar.com/fixed-deposit/icici-bank-fd-interest-rates/",
        ),
    },
    # Axis — home loan
    {
        "keywords": ("axis home loan", "axis housing loan"),
        "urls": (
            "https://www.bankbazaar.com/home-loan/axis-bank-home-loan-interest-rate.html",
            "https://www.paisabazaar.com/home-loan/axis-bank-home-loan-interest-rate/",
        ),
    },
    # Axis — personal loan
    {
        "keywords": ("axis personal loan", "axis bank personal loan"),
        "urls": (
            "https://www.bankbazaar.com/personal-loan/axis-bank-personal-loan-interest-rate.html",
            "https://www.paisabazaar.com/personal-loan/axis-bank-personal-loan/",
        ),
    },
    # Axis — fixed deposit
    {
        "keywords": ("axis fd", "axis fixed deposit", "axis deposit rate"),
        "urls": (
            "https://www.bankbazaar.com/fixed-deposit/axis-bank-fd-rates.html",
            "https://groww.in/fixed-deposit/axis-bank-fd-interest-rates",
        ),
    },
    # Cross-bank comparison queries
    {
        "keywords": ("compare home loan", "best home loan", "home loan comparison", "lowest home loan"),
        "urls": (
            "https://www.bankbazaar.com/home-loan-interest-rates.html",
            "https://www.paisabazaar.com/home-loan/",
        ),
    },
    {
        "keywords": ("compare fd", "best fd", "fd comparison", "highest fd", "best fixed deposit"),
        "urls": (
            "https://www.bankbazaar.com/fixed-deposit.html",
            "https://groww.in/fixed-deposit",
        ),
    },
    {
        "keywords": ("compare personal loan", "best personal loan", "lowest personal loan"),
        "urls": (
            "https://www.bankbazaar.com/personal-loan-interest-rates.html",
            "https://www.paisabazaar.com/personal-loan/",
        ),
    },
)

# ---------------------------------------------------------------------------
# Tier 3 — Bank official homepages (citation-only fallback)
# Used only when Tiers 1 and 2 return fewer than MAX_CANDIDATE_URLS pages.
# These are included so the user always has an authoritative URL to visit,
# even if the crawler cannot extract content from them.
# ---------------------------------------------------------------------------
BANK_HOMEPAGE_MAP: tuple[dict[str, Any], ...] = (
    {"keywords": ("sbi", "state bank of india"), "url": "https://www.sbi.co.in/"},
    {"keywords": ("hdfc",),                       "url": "https://www.hdfcbank.com/"},
    {"keywords": ("icici",),                      "url": "https://www.icicibank.com/"},
    {"keywords": ("axis",),                       "url": "https://www.axisbank.com/"},
    {"keywords": ("rbi", "reserve bank"),         "url": "https://www.rbi.org.in/"},
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    """Normalize URLs and resolve DuckDuckGo redirect wrappers.

    Preserves www. prefix so requests go to the correct hostname.
    www. is only stripped internally by _is_official_url/_is_aggregator_url
    for domain matching, not here.
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


def _is_official_url(url: str) -> bool:
    hostname = urlparse(url).netloc.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return any(
        hostname == domain.lstrip(".") or hostname.endswith(domain)
        for domain in OFFICIAL_DOMAINS
    )


def _is_aggregator_url(url: str) -> bool:
    hostname = urlparse(url).netloc.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in AGGREGATOR_DOMAINS)


def _is_low_quality_url(url: str) -> bool:
    hostname = urlparse(url).netloc.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in LOW_QUALITY_DOMAINS)


def _query_terms(query: str) -> list[str]:
    stop_words = {"a", "an", "and", "are", "for", "from", "is", "latest",
                  "of", "on", "the", "to", "what", "with", "give", "me", "tell"}
    terms = re.findall(r"[a-z0-9]+", query.lower())
    return [t for t in terms if len(t) > 2 and t not in stop_words]


def _mapped_rbi_urls(query: str) -> list[str]:
    query_lower = query.lower()
    urls: list[str] = []
    for source in RBI_SOURCE_MAP:
        if any(keyword in query_lower for keyword in source["keywords"]):
            urls.extend(source["urls"])
    return urls


def _mapped_aggregator_urls(query: str) -> list[str]:
    query_lower = query.lower()
    urls: list[str] = []
    for source in AGGREGATOR_SOURCE_MAP:
        if any(keyword in query_lower for keyword in source["keywords"]):
            urls.extend(source["urls"])
            break  # use the first matching entry only to avoid URL explosion
    return urls


def _generic_homepage_urls(query: str) -> list[str]:
    query_lower = query.lower()
    urls: list[str] = []
    for entry in BANK_HOMEPAGE_MAP:
        if any(keyword in query_lower for keyword in entry["keywords"]):
            urls.append(entry["url"])
    return urls


def _dedupe_urls(urls: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in urls:
        url = _clean_url(candidate)
        if not url or _is_low_quality_url(url):
            continue
        # Use www-stripped version as dedup key so www.x.com and x.com are treated as the same
        dedup_key = re.sub(r"^(https?://)www\.", r"", url)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        unique.append(url)
    # Sort: RBI/official first, then aggregators, then everything else
    def _sort_key(u: str) -> int:
        if _is_official_url(u):
            return 0
        if _is_aggregator_url(u):
            return 1
        return 2
    unique.sort(key=_sort_key)
    return unique


def _resolve_duckduckgo_urls(query: str) -> list[str]:
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
        href = anchor.get("href")
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


def _candidate_urls(query: str) -> list[str]:
    """Build candidate URL list with four-tier priority:

    Tier 1a — RBI direct URLs (static, always crawlable) for RBI queries.
    Tier 1b — Aggregator URLs per bank+product (static HTML with rate tables).
    Tier 2  — DuckDuckGo results (catches anything not in maps, returns aggregators naturally).
    Tier 3  — Bank official homepages (citation-only last resort).
    """
    candidates: list[str] = []

    # Tier 1a — RBI direct
    candidates.extend(_mapped_rbi_urls(query))

    # Tier 1b — aggregator pages for the specific bank+product
    for url in _mapped_aggregator_urls(query):
        if url not in candidates:
            candidates.append(url)

    # Tier 2 — DuckDuckGo
    try:
        ddg_urls = _resolve_duckduckgo_urls(query)
        candidates.extend(url for url in ddg_urls if url not in candidates)
    except Exception as exc:
        _debug(f"DuckDuckGo resolver failed: {exc}")

    # Tier 3 — generic bank homepage (citation fallback only)
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
    return _clean_text(urlparse(url).netloc or "Official source", limit=90)


def _extract_page_lines(soup: BeautifulSoup) -> list[str]:
    for element in soup(["script", "style", "noscript", "nav", "footer", "header", "svg"]):
        element.decompose()

    root = soup.find("main") or soup.find("article") or soup.body or soup
    lines: list[str] = []
    for element in root.find_all(
        ["h1", "h2", "h3", "p", "li", "td", "th", "tr", "div", "span"], limit=420
    ):
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

    # Special case: extract the exact repo rate sentence
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
        if any(marker in line_lower for marker in ("rate", "interest", "repo", "charge", "fee", "rbi", "loan", "announc", "document", "eligib", "kyc")):
            score += 1
        if "%" in line:
            score += 2  # percentage signs are the strongest signal for rate data
        scored_lines.append((score, -index, line))

    scored_lines.sort(reverse=True)
    chosen = [line for score, _index, line in scored_lines if score > 0][:4]
    if not chosen:
        chosen = lines[:4]
    return _clean_text(" ".join(chosen), limit=SNIPPET_LIMIT)


# ---------------------------------------------------------------------------
# Snippet quality validation
# ---------------------------------------------------------------------------

# Query intent classes
_RATE_SIGNALS = ("rate", "interest", "fd", "fixed deposit", "deposit", "loan", "emi", "roi", "per annum")
_DOC_SIGNALS  = ("document", "kyc", "eligib", "criteria", "required", "minimum balance", "open account", "account open")


def _query_intent(query: str) -> str:
    """Classify query intent: 'rate', 'document', or 'general'."""
    q = query.lower()
    if any(s in q for s in _DOC_SIGNALS):
        return "document"
    if any(s in q for s in _RATE_SIGNALS):
        return "rate"
    return "general"


def _snippet_has_useful_content(snippet: str, query: str) -> bool:
    """Validate snippet quality based on query intent.

    rate     → must contain '%' or a numeric rate pattern
    document → must contain a document/eligibility keyword (no % required)
    general  → any non-empty snippet accepted
    """
    if not snippet:
        return False

    intent = _query_intent(query)

    if intent == "rate":
        has_percent = "%" in snippet
        has_number  = bool(re.search(
            r"\d+(?:\.\d+)?\s*(?:p\.a|per\s*annum|year|month|day|lakh|crore|years|months)",
            snippet, re.IGNORECASE,
        ))
        return has_percent or has_number

    if intent == "document":
        doc_keywords = ("aadhaar", "pan", "passport", "address proof", "identity", "photograph",
                        "kyc", "document", "eligib", "income proof", "salary", "minimum", "balance")
        return any(kw in snippet.lower() for kw in doc_keywords)

    return True  # general intent — accept any non-empty snippet


# ---------------------------------------------------------------------------
# Crawl a single page
# ---------------------------------------------------------------------------

def _crawl_page(url: str, query: str) -> dict[str, str] | None:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        response.raise_for_status()
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

    if not _snippet_has_useful_content(snippet, query):
        _debug(f"Skipping low-content snippet for {url}")
        return None

    return {
        "title": _title_from_soup(soup, url),
        "url":   _clean_url(url),
        "content": snippet,
    }


# ---------------------------------------------------------------------------
# Format results for the LLM summarizer
# ---------------------------------------------------------------------------

def _format_search_results(
    results: list[dict[str, str]],
    failed_official_urls: list[str] | None = None,
) -> str:
    """Format crawled results into a compact block for the LLM summarizer.

    failed_official_urls are official/bank pages that were reached but returned
    JS-rendered or empty content. They are appended as UNVERIFIED_OFFICIAL_URL
    lines so the LLM can still cite them and direct the user to verify there.
    """
    failed_official_urls = failed_official_urls or []

    if not results and not failed_official_urls:
        return "No useful web search results were found."

    sections: list[str] = []

    for index, item in enumerate(results[:MAX_SEARCH_RESULTS], start=1):
        sections.append(
            f"{index}. {item['title']}\nURL: {item['url']}\nSnippet: {item['content']}"
        )

    # Preserve bank official URLs where content could not be extracted,
    # so the user always has an authoritative source to verify figures.
    for url in failed_official_urls[:3]:
        sections.append(f"UNVERIFIED_OFFICIAL_URL: {url}")

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# LangChain tool
# ---------------------------------------------------------------------------

@tool
def web_search(query: str):
    """Crawl banking aggregator and official sources for live banking data, current loan rates, FD rates, latest RBI announcements, and banking information not available in local knowledge."""
    _debug("web_search crawler called")

    results: list[dict[str, str]] = []
    # Official/bank pages that were reached but had JS-rendered/empty content —
    # preserved as citations so the user always has somewhere to verify.
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
            clean = _clean_url(url)
            if clean:
                failed_official_urls.append(clean)
        if len(results) == MAX_SEARCH_RESULTS:
            break

    results.sort(key=lambda item: (0 if _is_official_url(item["url"]) else 1 if _is_aggregator_url(item["url"]) else 2))
    return _format_search_results(results, failed_official_urls)


WEB_SEARCH_TOOL = web_search