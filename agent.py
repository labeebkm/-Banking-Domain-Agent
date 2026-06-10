"""Compatibility entry point for the banking assistant CLI."""

from banking_agent.cli import main
from banking_agent.context import get_banking_context
from banking_agent.guard import is_banking_related
from banking_agent.knowledge import (
    get_banking_products,
    get_banking_technology,
    get_interest_rates,
    get_regulatory_info,
)
from banking_agent.service import build_agent, run_agent

__all__ = [
    "build_agent",
    "get_banking_context",
    "get_banking_products",
    "get_banking_technology",
    "get_interest_rates",
    "get_regulatory_info",
    "is_banking_related",
    "run_agent",
]


if __name__ == "__main__":
    main()
