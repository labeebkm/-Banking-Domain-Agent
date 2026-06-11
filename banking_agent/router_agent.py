"""Router agent that answers locally or delegates live-data questions."""

import json
import re
from typing import Any

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from banking_agent.config import GROQ_API_KEY, MODEL_NAME, MODEL_TEMPERATURE
from banking_agent.guard import is_banking_related
from banking_agent.prompts import OFF_TOPIC_RESPONSE, ROUTER_SYSTEM_PROMPT
from banking_agent.search_agent import build_search_agent, run_search_agent
from banking_agent.tools import BANKING_TOOLS


@tool
def delegate_to_search_agent(query: str) -> str:
    """Delegate current/live banking, loan, RBI, rate, or bank-specific product questions to the Search Agent."""
    search_agent = build_search_agent()
    return run_search_agent(search_agent, query)


ROUTER_TOOLS = [*BANKING_TOOLS, delegate_to_search_agent]
TOOL_CALL_PATTERN = re.compile(r"<function=(?P<name>\w+)\s*(?P<args>\{.*?\})</function>")
TOOL_BY_NAME = {tool.name: tool for tool in ROUTER_TOOLS}


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
