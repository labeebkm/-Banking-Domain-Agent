"""Tests for the banking calculator MCP tool logic."""

import unittest

from mcp_server.calculators import (
    calculate_fd_maturity,
    check_loan_eligibility,
    compare_loan_options,
)
from banking_agent.router_agent import RouterAgent, run_router_agent


class McpCalculatorTests(unittest.TestCase):
    def test_check_loan_eligibility_returns_expected_fields(self) -> None:
        result = check_loan_eligibility(
            monthly_income=80000,
            monthly_obligations=15000,
            requested_loan_amount=2500000,
            annual_rate=8.5,
            tenure_years=20,
        )

        self.assertIn("eligibility_status", result)
        self.assertIn("estimated_emi", result)
        self.assertIn("foir_dti_ratio", result)
        self.assertIn("max_affordable_emi", result)
        self.assertEqual(result["eligibility_status"], "eligible")

    def test_calculate_fd_maturity_uses_compound_interest(self) -> None:
        result = calculate_fd_maturity(
            principal=500000,
            annual_rate=7,
            tenure_years=5,
            compounding_frequency=4,
        )

        self.assertAlmostEqual(result["maturity_amount"], 707389.10, places=2)
        self.assertAlmostEqual(result["interest_earned"], 207389.10, places=2)

    def test_compare_loan_options_selects_lowest_total_payment(self) -> None:
        result = compare_loan_options(
            [
                {"principal": 1000000, "annual_rate": 8.5, "tenure_years": 20},
                {"principal": 1000000, "annual_rate": 9.0, "tenure_years": 15},
                {"principal": 1000000, "annual_rate": 8.75, "tenure_years": 18},
            ]
        )

        self.assertEqual(len(result["comparison"]), 3)
        self.assertEqual(result["best_option"]["option"], 2)

    def test_invalid_inputs_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            calculate_fd_maturity(
                principal=0,
                annual_rate=7,
                tenure_years=5,
                compounding_frequency=4,
            )

    def test_sync_router_runner_supports_async_graph(self) -> None:
        class AsyncGraph:
            async def ainvoke(self, payload: dict, config: dict | None = None) -> dict:
                return {"messages": [type("Message", (), {"content": "async graph ok"})()]}

        agent = RouterAgent(graph=AsyncGraph(), tools=[], tools_by_name={})

        result = run_router_agent(
            agent,
            "What will be the maturity amount for a 5 lakh FD at 7% for 5 years with quarterly compounding?",
        )

        self.assertEqual(result, "async graph ok")


if __name__ == "__main__":
    unittest.main()
