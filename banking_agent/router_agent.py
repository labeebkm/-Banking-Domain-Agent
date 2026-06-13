"""Router agent that answers locally or delegates live-data questions."""

import json
import re
from typing import Any

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from banking_agent.config import DEBUG_AGENTS, GROQ_API_KEY, MODEL_NAME, MODEL_TEMPERATURE
from banking_agent.guard import is_banking_related
from banking_agent.prompts import OFF_TOPIC_RESPONSE, ROUTER_SYSTEM_PROMPT
from banking_agent.search_agent import build_search_agent, run_search_agent
from banking_agent.tools import BANKING_TOOLS


@tool
def delegate_to_search_agent(query: str) -> str:
    """Delegate current/live banking, loan, RBI, rate, or bank-specific product questions to the Search Agent."""
    _debug("Delegating to Search Agent")
    search_agent = build_search_agent()
    return run_search_agent(search_agent, query)


ROUTER_TOOLS = [*BANKING_TOOLS, delegate_to_search_agent]
TOOL_CALL_PATTERN = re.compile(r"<function=(?P<name>\w+)\s*(?P<args>\{.*?\})</function>")
TOOL_BY_NAME = {tool.name: tool for tool in ROUTER_TOOLS}
RECURSION_LIMIT = 5
LIVE_SEARCH_TERMS = (
    "latest",
    "current",
    "today",
    "now",
    "recent",
    "live",
    "offer",
    "offers",
    "2025",
    "2026",
)
BANK_SPECIFIC_TERMS = (
    "sbi",
    "state bank of india",
    "hdfc",
    "icici",
    "axis bank",
    "kotak",
    "pnb",
    "bank of baroda",
)


def _debug(message: str) -> None:
    if DEBUG_AGENTS:
        print(message)


def _is_rate_limit_error(error: Exception) -> bool:
    error_text = str(error).lower()
    return "429" in error_text or "rate_limit" in error_text or "rate limit" in error_text


def _is_obvious_non_banking_question(user_input: str) -> bool:
    """Catch common non-banking questions that contain ambiguous banking keywords."""
    question_lower = user_input.lower()
    if "capital of" not in question_lower:
        return False

    banking_terms = (
        "bank",
        "banking",
        "finance",
        "financial",
        "rbi",
        "capital adequacy",
        "capital ratio",
        "tier 1",
        "basel",
    )
    return not any(term in question_lower for term in banking_terms)


def _needs_live_search(user_input: str) -> bool:
    """Route live, recent, and bank-specific details without extra LLM loops."""
    question_lower = user_input.lower()
    if any(term in question_lower for term in LIVE_SEARCH_TERMS):
        return True
    if any(term in question_lower for term in BANK_SPECIFIC_TERMS):
        return any(
            term in question_lower
            for term in ("loan", "rate", "interest", "product", "account", "card", "rbi", "repo")
        )
    return False


def _answer_with_local_tool(user_input: str) -> str | None:
    """Answer obvious static banking questions directly to save Groq tokens."""
    question_lower = user_input.lower()
    tool = None
    if any(term in question_lower for term in ("savings account", "current account", "demat", "nri account", "card")):
        tool = TOOL_BY_NAME["get_banking_products"]
    elif any(term in question_lower for term in ("upi", "neft", "rtgs", "swift", "core banking", "open banking")):
        tool = TOOL_BY_NAME["get_banking_technology"]
    elif any(term in question_lower for term in ("kyc", "basel", "dicgc", "npa", "fdic", "ifrs", "repo rate", "rbi")):
        tool = TOOL_BY_NAME["get_regulatory_info"]
    elif any(term in question_lower for term in ("interest", "rate", "fixed deposit", "fd", "home loan", "personal loan", "car loan")):
        tool = TOOL_BY_NAME["get_interest_rates"]

    if tool is None:
        return None

    return f"According to the local banking knowledge tool, {tool.invoke({'query': user_input})}"


def build_router_agent() -> Any:
    """Build the Router Agent with local tools and Search Agent delegation."""
    llm = ChatGroq(
        model=MODEL_NAME,
        temperature=MODEL_TEMPERATURE,
        api_key=GROQ_API_KEY,
    )
    llm_with_tools = llm.bind_tools(ROUTER_TOOLS, tool_choice="auto")
    return create_react_agent(
        llm_with_tools,
        tools=ROUTER_TOOLS,
        prompt=ROUTER_SYSTEM_PROMPT,
    )


def _recover_failed_tool_call(error: Exception) -> str | None:
    """Recover when Groq reports a malformed tool call that still names a valid tool."""
    match = TOOL_CALL_PATTERN.search(str(error))
    if not match:
        return None

    tool = TOOL_BY_NAME.get(match.group("name"))
    if tool is None:
        return None

    try:
        tool_args = json.loads(match.group("args"))
        tool_result = tool.invoke(tool_args)
    except Exception:
        return None

    return (
        "According to the selected banking tool, "
        f"{tool_result} "
        "Please verify current rates, announcements, or regulations against the latest official source."
    )


def run_router_agent(agent: Any, user_input: str) -> str:
    """Run the router agent after applying the banking-domain guard."""
    _debug("Router Agent called")
    if not is_banking_related(user_input):
        return OFF_TOPIC_RESPONSE
    if _is_obvious_non_banking_question(user_input):
        return OFF_TOPIC_RESPONSE

    if _needs_live_search(user_input):
        return delegate_to_search_agent.invoke({"query": user_input})

    local_response = _answer_with_local_tool(user_input)
    if local_response is not None:
        return local_response

    try:
        response = agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config={"recursion_limit": RECURSION_LIMIT},
        )
    except Exception as exc:
        recovered_response = _recover_failed_tool_call(exc)
        if recovered_response is not None:
            return recovered_response

        if _is_rate_limit_error(exc):
            return (
                "I couldn't complete the banking request because the Groq rate limit was reached. "
                "Please try again later or verify current details with the latest official source."
            )

        return (
            "I couldn't complete the banking assistant request right now. "
            f"Please check your Groq API key, network, and model/tool configuration, then try again. Details: {exc}"
        )

    messages = response.get("messages", []) if isinstance(response, dict) else []
    if not messages:
        return "I couldn't produce a final banking response. Please try again."

    final_message = messages[-1]
    return getattr(final_message, "content", str(final_message))
