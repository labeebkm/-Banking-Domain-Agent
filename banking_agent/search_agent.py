"""Dedicated live-search banking agent."""

import json
import re
from typing import Any

from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from banking_agent.config import GROQ_API_KEY, MODEL_NAME, MODEL_TEMPERATURE
from banking_agent.prompts import SEARCH_SYSTEM_PROMPT
from banking_agent.search_tool import WEB_SEARCH_TOOL


TOOL_CALL_PATTERN = re.compile(r"<function=(?P<name>\w+)\s*(?P<args>\{.*?\})</function>")


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


def _recover_failed_search_tool_call(error: Exception) -> str | None:
    """Recover when the Search Agent emits a malformed web_search tool call."""
    match = TOOL_CALL_PATTERN.search(str(error))
    if not match or match.group("name") != WEB_SEARCH_TOOL.name:
        return None

    try:
        tool_args = json.loads(match.group("args"))
        tool_result = WEB_SEARCH_TOOL.invoke(tool_args)
    except Exception:
        return None

    return (
        "I searched live banking sources and found the following results. "
        "Please prefer official bank or regulator URLs when verifying current details.\n\n"
        f"{tool_result}"
    )


def run_search_agent(agent: Any, query: str) -> str:
    """Run the Search Agent and return its final summarized response."""
    try:
        response = agent.invoke({"messages": [{"role": "user", "content": query}]})
    except Exception as exc:
        recovered_response = _recover_failed_search_tool_call(exc)
        if recovered_response is not None:
            return recovered_response

        return (
            "I couldn't complete the live banking search right now. "
            "Please verify the details with the latest official bank or regulator source. "
            f"Details: {exc}"
        )

    messages = response.get("messages", []) if isinstance(response, dict) else []
    if not messages:
        return (
            "I couldn't find a useful live-search answer. Please verify with the "
            "latest official bank or regulator source."
        )

    final_message = messages[-1]
    return getattr(final_message, "content", str(final_message))
