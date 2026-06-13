"""Dedicated live-search banking agent."""

import json
import re
from typing import Any

from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from banking_agent.config import DEBUG_AGENTS, GROQ_API_KEY, MODEL_NAME, MODEL_TEMPERATURE
from banking_agent.prompts import QUERY_REWRITE_PROMPT, SEARCH_SYSTEM_PROMPT
from banking_agent.search_tool import WEB_SEARCH_TOOL


TOOL_CALL_PATTERN = re.compile(r"<function=(?P<name>\w+)\s*(?P<args>\{.*?\})</function>")
RECURSION_LIMIT = 5
SUMMARY_INPUT_LIMIT = 1800
SOURCE_URL_PATTERN = re.compile(r"URL:\s*(?P<url>\S+)")
QUERY_REWRITE_LIMIT = 160


def _debug(message: str) -> None:
    if DEBUG_AGENTS:
        print(message)


def _is_rate_limit_error(error: Exception) -> bool:
    error_text = str(error).lower()
    return "429" in error_text or "rate_limit" in error_text or "rate limit" in error_text


def _clean_output(text: str) -> str:
    """Keep generated answers safe for the Windows console."""
    return text.encode("ascii", errors="ignore").decode("ascii")


def build_search_query(user_query: str) -> str:
    """Use the configured model to rewrite a banking question for the crawler."""
    try:
        llm = ChatGroq(
            model=MODEL_NAME,
            temperature=0,
            api_key=GROQ_API_KEY,
        )
        response = llm.invoke(
            [
                ("system", QUERY_REWRITE_PROMPT),
                ("human", f"User: {user_query}\nSearch query:"),
            ]
        )
    except Exception:
        return f"{user_query} official latest banking"

    rewritten_query = getattr(response, "content", str(response)).strip()
    rewritten_query = rewritten_query.replace('"', "").replace("'", "")
    rewritten_query = rewritten_query.splitlines()[0].strip()
    rewritten_query = re.sub(r"^(search query|query)\s*:\s*", "", rewritten_query, flags=re.IGNORECASE)
    if not rewritten_query:
        return f"{user_query} official latest banking"
    return rewritten_query[:QUERY_REWRITE_LIMIT]


def _extract_source_urls(search_results: str) -> list[str]:
    """Extract up to three unique source URLs from compact crawler results."""
    urls: list[str] = []
    seen: set[str] = set()
    for match in SOURCE_URL_PATTERN.finditer(search_results):
        url = match.group("url").strip()
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
        if len(urls) == 3:
            break
    return urls


def _format_source_list(urls: list[str]) -> str:
    if not urls:
        return "Sources:\nNo source URLs were available from the search results."
    return "Sources:\n" + "\n".join(f"{index}. {url}" for index, url in enumerate(urls, start=1))


def _finalize_summary(summary: str, search_results: str) -> str:
    """Use the LLM answer but force sources to come from crawler results."""
    urls = _extract_source_urls(search_results)
    answer = re.split(r"\n\s*Sources\s*:", summary, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    if not answer.lower().startswith("answer:"):
        answer = f"Answer:\n{answer}"
    return _clean_output(f"{answer}\n\n{_format_source_list(urls)}")


def _fallback_summary(search_results: str) -> str:
    """Return a concise non-raw fallback if LLM summarization is unavailable."""
    urls = _extract_source_urls(search_results)
    return (
        "Answer:\n"
        "I found current banking sources, but I could not generate a confident summarized answer right now. "
        "Please verify the latest rate, date, eligibility, and product details on the official bank or regulator source before acting.\n\n"
        f"{_format_source_list(urls)}"
    )


def _is_repo_rate_query(query: str) -> bool:
    query_lower = query.lower()
    return "repo rate" in query_lower or ("rbi" in query_lower and "repo" in query_lower)


def _has_recent_context(search_results: str) -> bool:
    """Require a recent date signal before treating policy-rate snippets as latest."""
    result_lower = search_results.lower()
    return any(marker in result_lower for marker in ("2026", "2025", "current", "latest"))


def _repo_rate_uncertain_summary(search_results: str) -> str:
    urls = _extract_source_urls(search_results)
    return (
        "Answer:\n"
        "The latest RBI policy repo rate could not be confidently verified from the available search snippets. "
        "Some snippets mention policy-rate information, but they do not provide enough recent context to safely treat it as the latest rate. "
        "Please verify the current policy repo rate on the official RBI website before relying on it.\n\n"
        f"{_format_source_list(urls)}"
    )


def _summarize_search_results(query: str, search_results: str) -> str:
    """Use one lightweight LLM call to turn compact crawler results into an answer."""
    llm = ChatGroq(
        model=MODEL_NAME,
        temperature=MODEL_TEMPERATURE,
        api_key=GROQ_API_KEY,
    )
    compact_results = search_results[:SUMMARY_INPUT_LIMIT]
    prompt = f"""
User query:
{query}

Compact crawler results:
{compact_results}

Write the final response in exactly this format:

Answer:
<3-5 concise sentences. Use only facts supported by the crawler snippets. Ignore navigation, footer, cookie, menu, login, and boilerplate text. Prefer official bank, RBI, regulator, or government URLs. If an official bank/RBI source is present, say it is the authoritative source. Do not invent exact rates if the snippets do not clearly provide them. If the results are insufficient, say the detail could not be confidently verified and advise checking the official source.>

Sources:
1. <url>
2. <url>
3. <url>

Use at most 3 source URLs and do not include duplicate URLs.
For repo-rate questions, do not treat reverse repo rate, MSF rate, or Bank Rate as the RBI policy repo rate.
Do not mention your knowledge cutoff. Do not use sources outside the compact crawler results.
"""
    response = llm.invoke(
        [
            (
                "system",
                "You are a concise banking assistant summarizing compact crawler snippets. Do not call tools.",
            ),
            ("human", prompt),
        ]
    )
    return getattr(response, "content", str(response)).strip()


def build_search_agent() -> Any:
    """Build the Search Agent, which can only use the web_search tool."""
    llm = ChatGroq(
        model=MODEL_NAME,
        temperature=MODEL_TEMPERATURE,
        api_key=GROQ_API_KEY,
    )
    llm_with_tools = llm.bind_tools([WEB_SEARCH_TOOL], tool_choice="auto")
    return create_react_agent(
        llm_with_tools,
        tools=[WEB_SEARCH_TOOL],
        prompt=SEARCH_SYSTEM_PROMPT,
    )


def _recover_failed_search_tool_call(error: Exception, query: str) -> str | None:
    """Recover when the Search Agent emits a malformed web_search tool call."""
    match = TOOL_CALL_PATTERN.search(str(error))
    if not match or match.group("name") != WEB_SEARCH_TOOL.name:
        return None

    try:
        tool_args = json.loads(match.group("args"))
        tool_result = WEB_SEARCH_TOOL.invoke(tool_args)
    except Exception:
        return None

    try:
        summary = _summarize_search_results(query, tool_result)
        return _finalize_summary(summary, tool_result)
    except Exception:
        return _fallback_summary(tool_result)


def run_search_agent(agent: Any, query: str) -> str:
    """Run the Search Agent and return its final summarized response."""
    _debug("Search Agent called")
    try:
        # Single search call avoids repeated ReAct loops and keeps live queries cheap.
        search_query = build_search_query(query)
        _debug(f"Rewritten search query: {search_query}")
        tool_result = WEB_SEARCH_TOOL.invoke({"query": search_query})
    except Exception as exc:
        recovered_response = _recover_failed_search_tool_call(exc, query)
        if recovered_response is not None:
            return recovered_response

        if _is_rate_limit_error(exc):
            return (
                "The live banking search could not be completed because the Groq rate limit was reached. "
                "Please try again later or verify the details with the latest official bank or regulator source."
            )

        return (
            "I couldn't complete the live banking search right now. "
            "Please verify the details with the latest official bank or regulator source. "
            f"Details: {exc}"
        )

    if not tool_result:
        return (
            "I couldn't find a useful live-search answer. Please verify with the "
            "latest official bank or regulator source."
        )

    if "No useful web search results were found" in tool_result or "Live search is unavailable" in tool_result:
        return _fallback_summary(tool_result)

    if _is_repo_rate_query(query) and not _has_recent_context(tool_result):
        return _repo_rate_uncertain_summary(tool_result)

    try:
        summary = _summarize_search_results(query, tool_result)
        return _finalize_summary(summary, tool_result)
    except Exception as exc:
        if _is_rate_limit_error(exc):
            return (
                "Answer:\n"
                "The live banking search completed, but the summarized answer could not be generated because the Groq rate limit was reached. "
                "Please try again later or verify the latest details with the official bank or regulator source.\n\n"
                f"{_format_source_list(_extract_source_urls(tool_result))}"
            )
        return _fallback_summary(tool_result)
