"""Labeeb Banking Loan and FD Calculator MCP server."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_server.calculators import (
    AmountInput,
    calculate_fd_maturity as calculate_fd_maturity_logic,
    check_loan_eligibility as check_loan_eligibility_logic,
    compare_loan_options as compare_loan_options_logic,
)

mcp = FastMCP("labeeb-banking-loan-fd-calculator")


@mcp.tool()
def check_loan_eligibility(
    monthly_income: AmountInput,
    monthly_obligations: AmountInput,
    requested_loan_amount: AmountInput,
    annual_rate: float,
    tenure_years: float,
) -> dict[str, Any]:
    """Check loan eligibility. Rupee amounts may be numbers or Indian units: 25 lakh = 2500000, 1 crore = 10000000."""
    try:
        return check_loan_eligibility_logic(
            monthly_income=monthly_income,
            monthly_obligations=monthly_obligations,
            requested_loan_amount=requested_loan_amount,
            annual_rate=annual_rate,
            tenure_years=tenure_years,
        )
    except ValueError as exc:
        return {"error": str(exc)}


@mcp.tool()
def calculate_fd_maturity(
    principal: AmountInput,
    annual_rate: float,
    tenure_years: float,
    compounding_frequency: int = 4,
) -> dict[str, float] | dict[str, str]:
    """Calculate FD maturity. Rupee principal may be a number or Indian units: 5 lakh = 500000, 1 crore = 10000000."""
    try:
        return calculate_fd_maturity_logic(
            principal=principal,
            annual_rate=annual_rate,
            tenure_years=tenure_years,
            compounding_frequency=compounding_frequency,
        )
    except ValueError as exc:
        return {"error": str(exc)}


@mcp.tool()
def compare_loan_options(options: list[dict[str, AmountInput]]) -> dict[str, Any]:
    """Compare loan options. Principal values may be numbers or Indian units such as 10 lakh or 1 crore."""
    try:
        return compare_loan_options_logic(options)
    except ValueError as exc:
        return {"error": str(exc)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
