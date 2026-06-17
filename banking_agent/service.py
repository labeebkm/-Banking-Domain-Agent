"""Core assistant service functions."""

from typing import Any

from banking_agent.router_agent import (
    build_router_agent,
    build_router_agent_async,
    run_router_agent,
    run_router_agent_async,
)


def build_two_agent_system() -> Any:
    """Build and return the router agent for the two-agent system."""
    return build_router_agent()


async def build_two_agent_system_async() -> Any:
    """Build and return the router agent from an async context."""
    return await build_router_agent_async()


def run_two_agent_system(agent: Any, user_input: str) -> str:
    """Run the two-agent system through the router agent."""
    return run_router_agent(agent, user_input)


async def run_two_agent_system_async(agent: Any, user_input: str) -> str:
    """Run the two-agent system through the async router agent path."""
    return await run_router_agent_async(agent, user_input)
