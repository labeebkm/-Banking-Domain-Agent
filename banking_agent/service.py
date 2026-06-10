"""Core assistant service functions."""

from typing import Any

from langchain_groq import ChatGroq

from banking_agent.config import GROQ_API_KEY, MODEL_NAME, MODEL_TEMPERATURE
from banking_agent.context import get_banking_context
from banking_agent.guard import is_banking_related
from banking_agent.prompts import OFF_TOPIC_RESPONSE, SYSTEM_PROMPT


def build_agent() -> ChatGroq:
    """Build and return the Groq chat model used by the assistant."""
    return ChatGroq(
        model=MODEL_NAME,
        temperature=MODEL_TEMPERATURE,
        api_key=GROQ_API_KEY,
    )


def run_agent(agent: Any, user_input: str) -> str:
    """Run the assistant with domain guard and selected banking context."""
    if not is_banking_related(user_input):
        return OFF_TOPIC_RESPONSE

    banking_context = get_banking_context(user_input)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Banking context:\n{banking_context}\n\nUser question: {user_input}",
        },
    ]

    try:
        response = agent.invoke(messages)
    except Exception as exc:
        return (
            "I couldn't get a response from Groq right now. "
            f"Please check your API key/network and try again. Details: {exc}"
        )

    return getattr(response, "content", str(response))
