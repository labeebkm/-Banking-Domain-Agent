"""Core assistant service functions."""

from typing import Any

from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from banking_agent.config import GROQ_API_KEY, MODEL_NAME, MODEL_TEMPERATURE
from banking_agent.guard import is_banking_related
from banking_agent.prompts import OFF_TOPIC_RESPONSE, SYSTEM_PROMPT
from banking_agent.tools import BANKING_TOOLS


def build_agent() -> Any:
    llm = ChatGroq(
        model=MODEL_NAME,
        temperature=MODEL_TEMPERATURE,
        api_key=GROQ_API_KEY,
    )
    # Pass raw llm — create_react_agent handles bind_tools internally
    return create_react_agent(llm, tools=BANKING_TOOLS, prompt=SYSTEM_PROMPT)


def run_agent(agent: Any, user_input: str) -> str:
    """Run the assistant with domain guard and LLM-driven tool calling."""
    if not is_banking_related(user_input):
        return OFF_TOPIC_RESPONSE

    try:
        response = agent.invoke({"messages": [{"role": "user", "content": user_input}]})
    except Exception as exc:
        return (
            "I couldn't complete the banking assistant request right now. "
            f"Please check your API key, network, and model/tool configuration, then try again. Details: {exc}"
        )

    messages = response.get("messages", []) if isinstance(response, dict) else []
    if not messages:
        return "I couldn't produce a final banking response. Please try again."

    final_message = messages[-1]
    return getattr(final_message, "content", str(final_message))
