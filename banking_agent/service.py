"""Core assistant service functions."""

import json
import re
from typing import Any

from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from banking_agent.config import GROQ_API_KEY, MODEL_NAME, MODEL_TEMPERATURE
from banking_agent.guard import is_banking_related
from banking_agent.prompts import OFF_TOPIC_RESPONSE, SYSTEM_PROMPT
from banking_agent.tools import BANKING_TOOLS


TOOL_CALL_PATTERN = re.compile(r"<function=(?P<name>\w+)(?P<args>\{.*?\})</function>")
TOOL_BY_NAME = {tool.name: tool for tool in BANKING_TOOLS}


def build_agent() -> Any:
    """Build and return the LangGraph ReAct banking agent."""
    llm = ChatGroq(
        model=MODEL_NAME,
        temperature=MODEL_TEMPERATURE,
        api_key=GROQ_API_KEY,
    )
    llm_with_tools = llm.bind_tools(BANKING_TOOLS, tool_choice="auto")
    return create_react_agent(llm_with_tools, tools=BANKING_TOOLS, prompt=SYSTEM_PROMPT)


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
        "According to the local banking knowledge tool, "
        f"{tool_result} "
        "Please verify current rates or regulations against the latest official source."
    )


def run_agent(agent: Any, user_input: str) -> str:
    """Run the assistant with domain guard and LLM-driven tool calling."""
    if not is_banking_related(user_input):
        return OFF_TOPIC_RESPONSE

    try:
        response = agent.invoke({"messages": [{"role": "user", "content": user_input}]})
    except Exception as exc:
        recovered_response = _recover_failed_tool_call(exc)
        if recovered_response is not None:
            return recovered_response

        return (
            "I couldn't complete the banking assistant request right now. "
            f"Please check your API key, network, and model/tool configuration, then try again. Details: {exc}"
        )

    messages = response.get("messages", []) if isinstance(response, dict) else []
    if not messages:
        return "I couldn't produce a final banking response. Please try again."

    final_message = messages[-1]
    return getattr(final_message, "content", str(final_message))
