"""Focused tests for deterministic local router shortcuts."""

import unittest

from banking_agent.router_agent import RouterAgent, run_router_agent


class RouterLocalRoutingTests(unittest.TestCase):
    def test_concept_questions_use_local_shortcuts_without_graph(self) -> None:
        class FailingGraph:
            async def ainvoke(self, payload: dict, config: dict | None = None) -> dict:
                raise AssertionError("Graph should not be used for deterministic local shortcut questions.")

        agent = RouterAgent(graph=FailingGraph(), tools=[], tools_by_name={})

        cases = [
            (
                "What are the advantages and disadvantages of home loans?",
                "Advantages of home loans include",
            ),
            (
                "Explain the difference between secured and unsecured loans.",
                "A secured loan is backed by collateral",
            ),
            (
                "How does inflation affect bank interest rates?",
                "Inflation often pushes central banks",
            ),
            (
                "What banking products are suitable for a salaried person?",
                "Suitable banking products for a salaried person",
            ),
        ]

        for question, expected_fragment in cases:
            with self.subTest(question=question):
                response = run_router_agent(agent, question)
                self.assertIn(expected_fragment, response)


if __name__ == "__main__":
    unittest.main()
