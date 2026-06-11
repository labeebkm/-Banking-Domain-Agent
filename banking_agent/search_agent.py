"""Dedicated live-search banking agent."""

from typing import Any

from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from banking_agent.config import GROQ_API_KEY, MODEL_NAME, MODEL_TEMPERATURE
from banking_agent.search_tool import WEB_SEARCH_TOOL


SEARCH_SYSTEM_PROMPT = """
You are a live-search banking and finance assistant.

Rules:
- Only answer banking and finance questions.
- Always use the web_search tool before answering.
- Cite source URLs from the web_search tool result in the response.
- If search returns no useful results, say so honestly.
- Be concise, accurate, and clear.
"""


def build_search_agent() -> Any:
    """Build and return the dedicated Tavily-backed search agent."""
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
