"""Tests for the banking calculator MCP tool logic."""

import json
import unittest

from mcp_server.calculators import (
    calculate_fd_maturity,
    check_loan_eligibility,
    compare_loan_options,
    normalize_amount,
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

    def test_five_lakh_fd_uses_indian_unit_amount(self) -> None:
        result = calculate_fd_maturity(
            principal="5 lakh",
            annual_rate=7,
            tenure_years=5,
            compounding_frequency=4,
        )

        self.assertAlmostEqual(result["maturity_amount"], 707389.10, places=2)
        self.assertAlmostEqual(result["interest_earned"], 207389.10, places=2)
        self.assertEqual(result["principal"], 500000)
        self.assertIn("Interest earned: INR 2,07,389.10", result["formatted_summary"])

    def test_twenty_five_lakh_loan_amount_uses_indian_unit_amount(self) -> None:
        text_amount = check_loan_eligibility(
            monthly_income=80000,
            monthly_obligations=15000,
            requested_loan_amount="25 lakh",
            annual_rate=8.5,
            tenure_years=20,
        )
        numeric_amount = check_loan_eligibility(
            monthly_income=80000,
            monthly_obligations=15000,
            requested_loan_amount=2500000,
            annual_rate=8.5,
            tenure_years=20,
        )

        self.assertEqual(text_amount["estimated_emi"], numeric_amount["estimated_emi"])
        self.assertEqual(text_amount["eligibility_status"], numeric_amount["eligibility_status"])

    def test_one_crore_uses_indian_unit_amount(self) -> None:
        self.assertEqual(normalize_amount("1 crore"), 10000000)
        self.assertEqual(normalize_amount("1 cr"), 10000000)

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

    def test_loan_comparison_ten_lakh_nine_percent_fifteen_years(self) -> None:
        result = compare_loan_options(
            [
                {"principal": "10 lakh", "annual_rate": 9, "tenure_years": 15},
            ]
        )

        option = result["comparison"][0]
        self.assertEqual(option["principal"], 1000000)
        self.assertEqual(option["months"], 180)
        self.assertAlmostEqual(option["estimated_emi"], 10142.67, places=2)
        self.assertAlmostEqual(option["total_payment"], 1825680.60, places=2)
        self.assertAlmostEqual(option["total_interest"], 825680.60, places=2)

    def test_loan_comparison_ten_lakh_eight_point_five_percent_twenty_years(self) -> None:
        result = compare_loan_options(
            [
                {"principal": "10 lakh", "annual_rate": 8.5, "tenure_years": 20},
            ]
        )

        option = result["comparison"][0]
        self.assertEqual(option["principal"], 1000000)
        self.assertEqual(option["months"], 240)
        self.assertAlmostEqual(option["estimated_emi"], 8678.23, places=2)
        self.assertAlmostEqual(option["total_payment"], 2082775.20, places=2)
        self.assertAlmostEqual(option["total_interest"], 1082775.20, places=2)

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

    def test_router_prefers_calculator_formatted_summary(self) -> None:
        correct_summary = (
            "Principal: INR 5,00,000.00\n"
            "Maturity amount: INR 7,07,389.10\n"
            "Interest earned: INR 2,07,389.10"
        )

        class AsyncGraph:
            async def ainvoke(self, payload: dict, config: dict | None = None) -> dict:
                return {
                    "messages": [
                        type(
                            "ToolMessage",
                            (),
                            {
                                "name": "calculate_fd_maturity",
                                "content": json.dumps({"formatted_summary": correct_summary}),
                            },
                        )(),
                        type("Message", (), {"content": "Interest earned is INR 20,73,891"})(),
                    ]
                }

        agent = RouterAgent(graph=AsyncGraph(), tools=[], tools_by_name={})

        result = run_router_agent(
            agent,
            "What will be the maturity amount for a 5 lakh FD at 7% for 5 years with quarterly compounding?",
        )

        self.assertEqual(result, correct_summary)


if __name__ == "__main__":
    unittest.main()
