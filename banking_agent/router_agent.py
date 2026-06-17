"""Router agent that answers locally or delegates live-data questions."""

import asyncio
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from banking_agent.config import DEBUG_AGENTS, GROQ_API_KEY, MODEL_NAME, MODEL_TEMPERATURE
from banking_agent.guard import is_banking_related
from banking_agent.prompts import OFF_TOPIC_RESPONSE, ROUTER_SYSTEM_PROMPT
from banking_agent.search_agent import run_search_agent
from banking_agent.tools import BANKING_TOOLS


@tool
def delegate_to_search_agent(query: str) -> str:
    """Delegate current/live banking, loan, RBI, rate, or bank-specific product questions to the Search Agent."""
    _debug("Delegating to Search Agent")
    return run_search_agent(query)


LOCAL_ROUTER_TOOLS = [*BANKING_TOOLS, delegate_to_search_agent]
TOOL_CALL_PATTERN = re.compile(r"<function=(?P<name>\w+)\s*(?P<args>\{.*?\})</function>")
LOCAL_TOOL_BY_NAME = {tool.name: tool for tool in LOCAL_ROUTER_TOOLS}
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
MCP_SERVER_PATH = Path(__file__).resolve().parent.parent / "mcp_server" / "server.py"
MCP_CALCULATOR_TOOL_NAMES = {
    "check_loan_eligibility",
    "calculate_fd_maturity",
    "compare_loan_options",
}


@dataclass(frozen=True)
class RouterAgent:
    """Router graph plus the exact tool registry it was built with."""

    graph: Any
    tools: list[Any]
    tools_by_name: dict[str, Any]


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
    if _is_calculator_intent(question_lower):
        return None

    tool = None
    if "inflation" in question_lower:
        tool = LOCAL_TOOL_BY_NAME["get_regulatory_info"]
    elif any(term in question_lower for term in ("secured loan", "unsecured loan", "secured and unsecured", "collateral")):
        tool = LOCAL_TOOL_BY_NAME["get_banking_products"]
    elif "home loan" in question_lower and any(
        term in question_lower for term in ("advantage", "disadvantage", "pros", "cons", "benefit", "drawback")
    ):
        tool = LOCAL_TOOL_BY_NAME["get_banking_products"]
    elif "salaried" in question_lower and any(
        term in question_lower for term in ("suitable", "suit", "best", "recommend", "product", "products")
    ):
        tool = LOCAL_TOOL_BY_NAME["get_banking_products"]
    elif any(term in question_lower for term in ("savings account", "current account", "demat", "nri account", "card")):
        tool = LOCAL_TOOL_BY_NAME["get_banking_products"]
    elif any(term in question_lower for term in ("upi", "neft", "rtgs", "swift", "core banking", "open banking")):
        tool = LOCAL_TOOL_BY_NAME["get_banking_technology"]
    elif any(term in question_lower for term in ("kyc", "basel", "dicgc", "npa", "fdic", "ifrs", "repo rate", "rbi")):
        tool = LOCAL_TOOL_BY_NAME["get_regulatory_info"]
    elif any(term in question_lower for term in ("interest", "rate", "fixed deposit", "fd", "home loan", "personal loan", "car loan")):
        tool = LOCAL_TOOL_BY_NAME["get_interest_rates"]

    if tool is None:
        return None

    return f"According to the local banking knowledge tool, {tool.invoke({'query': user_input})}"


def _is_calculator_intent(question_lower: str) -> bool:
    """Return True for loan and FD calculations that should reach MCP tools."""
    calculator_terms = ("calculate", "calculator", "maturity", "eligible", "eligibility", "compare", "emi", "foir", "dti")
    product_terms = ("loan", "fd", "fixed deposit")
    return any(term in question_lower for term in calculator_terms) and any(term in question_lower for term in product_terms)


def _parse_compare_loan_options_query(user_input: str) -> list[dict[str, Any]]:
    """Parse simple natural-language loan comparison prompts into tool arguments."""
    option_pattern = re.compile(
        r"(?P<principal>(?:inr|rs\.?|rupees|₹)?\s*\d+(?:,\d{2,3})*(?:\.\d+)?\s*(?:lakh|lakhs|lac|lacs|crore|crores|cr)?)"
        r"\s+at\s+(?P<annual_rate>\d+(?:\.\d+)?)\s*%?\s+for\s+(?P<tenure_years>\d+(?:\.\d+)?)\s*years?",
        flags=re.IGNORECASE,
    )
    options: list[dict[str, Any]] = []
    for match in option_pattern.finditer(user_input):
        principal = re.sub(r"\s+", " ", match.group("principal")).strip()
        options.append(
            {
                "principal": principal,
                "annual_rate": float(match.group("annual_rate")),
                "tenure_years": float(match.group("tenure_years")),
            }
        )
    return options


def _try_compare_loan_options_shortcut(user_input: str, tools_by_name: dict[str, Any]) -> str | None:
    """Call compare_loan_options directly for clear natural-language compare prompts."""
    question_lower = user_input.lower()
    if "compare" not in question_lower or "loan" not in question_lower:
        return None

    compare_tool = tools_by_name.get("compare_loan_options")
    if compare_tool is None:
        return None

    options = _parse_compare_loan_options_query(user_input)
    if len(options) < 2:
        return None

    try:
        result = compare_tool.invoke({"options": options})
    except Exception:
        return None

    parsed_result = _coerce_tool_content(result)
    summary = _extract_formatted_summary(parsed_result)
    if summary is not None:
        return summary

    return str(result)


async def _load_mcp_tools() -> list[Any]:
    """Load MCP tools from the local stdio server."""
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError as exc:
        _debug(f"MCP tools unavailable because langchain-mcp-adapters is not installed: {exc}")
        return []

    client = MultiServerMCPClient(
        {
            "labeeb_banking_calculator": {
                "command": sys.executable,
                "args": [str(MCP_SERVER_PATH)],
                "transport": "stdio",
            }
        }
    )
    return await client.get_tools()


def _load_mcp_tools_sync() -> list[Any]:
    """Synchronously load async MCP tools for the existing CLI builder."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        try:
            return asyncio.run(_load_mcp_tools())
        except Exception as exc:
            _debug(f"MCP tools could not be loaded: {exc}")
            return []

    _debug("MCP tools were skipped because build_router_agent() was called inside an active event loop.")
    return []


def _build_router_agent_with_tools(router_tools: list[Any]) -> RouterAgent:
    """Build the router graph from a prepared tool list."""
    tools_by_name = {tool.name: tool for tool in router_tools}
    llm = ChatGroq(
        model=MODEL_NAME,
        temperature=MODEL_TEMPERATURE,
        api_key=GROQ_API_KEY,
    )
    llm_with_tools = llm.bind_tools(router_tools, tool_choice="auto")
    graph = create_react_agent(
        llm_with_tools,
        tools=router_tools,
        prompt=ROUTER_SYSTEM_PROMPT,
    )
    return RouterAgent(graph=graph, tools=router_tools, tools_by_name=tools_by_name)


async def build_router_agent_async() -> RouterAgent:
    """Build the Router Agent asynchronously with local, Search Agent, and MCP tools."""
    mcp_tools = await _load_mcp_tools()
    return _build_router_agent_with_tools([*LOCAL_ROUTER_TOOLS, *mcp_tools])


def build_router_agent() -> Any:
    """Build the Router Agent with local, Search Agent, and MCP tools."""
    mcp_tools = _load_mcp_tools_sync()
    return _build_router_agent_with_tools([*LOCAL_ROUTER_TOOLS, *mcp_tools])


def _recover_failed_tool_call(error: Exception, tools_by_name: dict[str, Any]) -> str | None:
    """Recover when Groq reports a malformed tool call that still names a valid tool."""
    match = TOOL_CALL_PATTERN.search(str(error))
    if not match:
        return None

    tool = tools_by_name.get(match.group("name"))
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


def _coerce_tool_content(content: Any) -> Any:
    """Parse common LangChain tool content shapes into Python values."""
    if isinstance(content, (dict, list)):
        return content
    if not isinstance(content, str):
        return None

    text = content.strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        return ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return None


def _extract_formatted_summary(value: Any) -> str | None:
    """Find a calculator formatted_summary in nested tool output."""
    if isinstance(value, dict):
        summary = value.get("formatted_summary")
        if isinstance(summary, str) and summary.strip():
            return summary
        for child in value.values():
            nested_summary = _extract_formatted_summary(child)
            if nested_summary is not None:
                return nested_summary
    elif isinstance(value, list):
        for item in value:
            nested_summary = _extract_formatted_summary(item)
            if nested_summary is not None:
                return nested_summary
    return None


def _extract_calculator_tool_summary(messages: list[Any]) -> str | None:
    """Return MCP calculator summaries directly to avoid LLM recalculation errors."""
    for message in reversed(messages):
        tool_name = getattr(message, "name", None)
        content = getattr(message, "content", None)
        parsed_content = _coerce_tool_content(content)
        summary = _extract_formatted_summary(parsed_content)
        if summary is None:
            continue
        if tool_name in MCP_CALCULATOR_TOOL_NAMES or tool_name is None:
            return summary
    return None


def _extract_final_response(response: Any) -> str:
    """Extract final assistant text from a LangGraph response."""
    messages = response.get("messages", []) if isinstance(response, dict) else []
    if not messages:
        return "I couldn't produce a final banking response. Please try again."

    calculator_summary = _extract_calculator_tool_summary(messages)
    if calculator_summary is not None:
        return calculator_summary

    final_message = messages[-1]
    return getattr(final_message, "content", str(final_message))


async def _run_router_graph_async(graph: Any, user_input: str) -> Any:
    """Run the router graph asynchronously so async MCP tools can execute."""
    return await graph.ainvoke(
        {"messages": [{"role": "user", "content": user_input}]},
        config={"recursion_limit": RECURSION_LIMIT},
    )


def _run_router_graph_sync(graph: Any, user_input: str) -> Any:
    """Run the async-capable router graph from the synchronous CLI path."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_run_router_graph_async(graph, user_input))

    raise RuntimeError(
        "run_router_agent() cannot run the async MCP-enabled graph inside an active event loop. "
        "Use run_router_agent_async() instead."
    )


async def run_router_agent_async(agent: Any, user_input: str) -> str:
    """Run the router agent asynchronously after applying the banking-domain guard."""
    _debug("Router Agent called")
    graph = agent.graph if isinstance(agent, RouterAgent) else agent
    tools_by_name = agent.tools_by_name if isinstance(agent, RouterAgent) else LOCAL_TOOL_BY_NAME

    if not is_banking_related(user_input):
        return OFF_TOPIC_RESPONSE
    if _is_obvious_non_banking_question(user_input):
        return OFF_TOPIC_RESPONSE

    if _needs_live_search(user_input):
        return delegate_to_search_agent.invoke({"query": user_input})

    local_response = _answer_with_local_tool(user_input)
    if local_response is not None:
        return local_response

    compare_shortcut_response = _try_compare_loan_options_shortcut(user_input, tools_by_name)
    if compare_shortcut_response is not None:
        return compare_shortcut_response

    try:
        response = await _run_router_graph_async(graph, user_input)
    except Exception as exc:
        recovered_response = _recover_failed_tool_call(exc, tools_by_name)
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

    return _extract_final_response(response)


def run_router_agent(agent: Any, user_input: str) -> str:
    """Run the router agent after applying the banking-domain guard."""
    _debug("Router Agent called")
    graph = agent.graph if isinstance(agent, RouterAgent) else agent
    tools_by_name = agent.tools_by_name if isinstance(agent, RouterAgent) else LOCAL_TOOL_BY_NAME

    if not is_banking_related(user_input):
        return OFF_TOPIC_RESPONSE
    if _is_obvious_non_banking_question(user_input):
        return OFF_TOPIC_RESPONSE

    if _needs_live_search(user_input):
        return delegate_to_search_agent.invoke({"query": user_input})

    local_response = _answer_with_local_tool(user_input)
    if local_response is not None:
        return local_response

    compare_shortcut_response = _try_compare_loan_options_shortcut(user_input, tools_by_name)
    if compare_shortcut_response is not None:
        return compare_shortcut_response

    try:
        response = _run_router_graph_sync(graph, user_input)
    except Exception as exc:
        recovered_response = _recover_failed_tool_call(exc, tools_by_name)
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

    return _extract_final_response(response)
