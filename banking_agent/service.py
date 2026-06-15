"""Core assistant service functions."""

from typing import Any

from banking_agent.router_agent import build_router_agent, run_router_agent


def build_two_agent_system() -> Any:
    """Build and return the router agent for the two-agent system."""
    return build_router_agent()


def run_two_agent_system(agent: Any, user_input: str) -> str:
    """Run the two-agent system through the router agent."""
    return run_router_agent(agent, user_input)