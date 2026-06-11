"""Router agent that chooses between local banking tools and live web search."""

import json
import re
from typing import Any

from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from banking_agent.config import GROQ_API_KEY, MODEL_NAME, MODEL_TEMPERATURE
from banking_agent.guard import is_banking_related
from banking_agent.prompts import OFF_TOPIC_RESPONSE
from banking_agent.search_tool import WEB_SEARCH_TOOL
from banking_agent.tools import BANKING_TOOLS


ROUTER_TOOLS = [*BANKING_TOOLS, WEB_SEARCH_TOOL]
TOOL_CALL_PATTERN = re.compile(r"<function=(?P<name>\w+)(?P<args>\{.*?\})</function>")
TOOL_BY_NAME = {tool.name: tool for tool in ROUTER_TOOLS}

ROUTER_SYSTEM_PROMPT = """
You are a banking and finance router assistant with access to local banking tools
and a live web_search tool.

Routing rules:
- Only answer banking and finance questions.
- Use local tools for general banking concepts, definitions, regulations, and product information:
  get_interest_rates, get_banking_products, get_regulatory_info, get_banking_technology.
- Use web_search for current or latest loan rates from specific banks.
- Use web_search for recent RBI announcements or policy changes.
- Use web_search for live market data or current interest rates.
- Use web_search for any question containing words like "latest", "current",
  "today", "now", "recent", "2025", or "2026".
- Never answer from memory. Always call a tool first.
- Cite tool results in the response.
- When using web_search, include the source URL(s) from the tool result in the final answer.
- If a tool result is insufficient, say so honestly and explain what should be verified.
"""


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


def build_router_agent() -> Any:
    """Build and return the router agent with local and web-search tools."""
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
    if not is_banking_related(user_input):
        return OFF_TOPIC_RESPONSE
    if _is_obvious_non_banking_question(user_input):
        return OFF_TOPIC_RESPONSE

    try:
        response = agent.invoke({"messages": [{"role": "user", "content": user_input}]})
    except Exception as exc:
        recovered_response = _recover_failed_tool_call(exc)
        if recovered_response is not None:
            return recovered_response

        return (
            "I couldn't complete the banking assistant request right now. "
            f"Please check your API key, network, Tavily key, and model/tool configuration, then try again. Details: {exc}"
        )

    messages = response.get("messages", []) if isinstance(response, dict) else []
    if not messages:
        return "I couldn't produce a final banking response. Please try again."

    final_message = messages[-1]
    return getattr(final_message, "content", str(final_message))
