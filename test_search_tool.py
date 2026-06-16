"""Focused regression tests for crawler extraction and validation."""

import unittest
from unittest.mock import Mock, patch

import requests
from bs4 import BeautifulSoup

from banking_agent import search_tool


class SearchToolTests(unittest.TestCase):
    def test_document_query_accepts_document_names_without_numbers(self) -> None:
        snippet = "Submit PAN, Aadhaar, address proof, and a recent photograph for KYC."
        self.assertTrue(search_tool._snippet_has_useful_content(snippet, "SBI savings account documents KYC"))

    def test_rate_query_still_requires_rate_data(self) -> None:
        self.assertFalse(search_tool._snippet_has_useful_content("Explore our fixed deposit products.", "ICICI FD interest rate"))
        self.assertTrue(search_tool._snippet_has_useful_content("Fixed deposit interest rate is 7.25% p.a.", "ICICI FD interest rate"))

    def test_eligibility_query_uses_eligibility_terms(self) -> None:
        self.assertTrue(
            search_tool._snippet_has_useful_content(
                "Resident individuals and minors are eligible to open this account.",
                "SBI savings account eligibility",
            )
        )

    def test_structured_extraction_reads_tables_and_json_ld(self) -> None:
        soup = BeautifulSoup(
            """
            <html><body>
              <table><tr><th>Tenure</th><th>Interest rate</th></tr><tr><td>1 year</td><td>7.25%</td></tr></table>
              <script type="application/ld+json">{"name":"ICICI Bank Fixed Deposit","description":"Senior citizen rate 7.75%"}</script>
            </body></html>
            """,
            "html.parser",
        )
        lines = search_tool._extract_page_lines(soup)
        combined = " ".join(lines)
        self.assertIn("1 year | 7.25%", combined)
        self.assertIn("Senior citizen rate 7.75%", combined)

    def test_product_relevance_rejects_unrelated_homepage_percentage(self) -> None:
        self.assertFalse(
            search_tool._snippet_matches_query(
                "Axis Bank offers savings returns up to 9.35%.",
                "Axis Bank personal loan interest rate",
                "Axis Bank Homepage",
                "https://axisbank.com",
            )
        )
        self.assertTrue(
            search_tool._snippet_matches_query(
                "Axis Bank personal loan interest rates start from 10.49%.",
                "Axis Bank personal loan interest rate",
                "Personal Loan Rates | Axis Bank",
                "https://axisbank.com/personal-loan",
            )
        )

    @patch("banking_agent.search_tool._resolve_duckduckgo_urls")
    def test_home_loan_queries_include_crawlable_rate_pages(self, ddg: Mock) -> None:
        ddg.return_value = []

        sbi_urls = search_tool._candidate_urls("latest SBI home loan interest rate official SBI")
        hdfc_urls = search_tool._candidate_urls("current HDFC home loan interest rate official HDFC Bank")
        icici_urls = search_tool._candidate_urls("latest ICICI Bank home loan interest rate official ICICI Bank")

        self.assertTrue(any("paisabazaar.com/home-loan/sbi-home-loan" in url for url in sbi_urls))
        self.assertTrue(any("paisabazaar.com/home-loan/hdfc-home-loan" in url for url in hdfc_urls))
        self.assertTrue(any("paisabazaar.com/home-loan/icici-home-loan" in url for url in icici_urls))

    @patch("banking_agent.search_tool.requests.get")
    def test_request_retries_once_with_split_timeout(self, get: Mock) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        get.side_effect = [requests.ReadTimeout("slow"), response]

        self.assertIs(search_tool._get_with_retry("https://example.com"), response)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args.kwargs["timeout"], (6, 15))

    @patch("banking_agent.search_tool._candidate_urls")
    @patch("banking_agent.search_tool._crawl_page")
    def test_failed_official_url_is_preserved_as_unverified(self, crawl: Mock, candidates: Mock) -> None:
        candidates.return_value = ["https://sbi.co.in/web/interest-rates/deposit-rates"]
        crawl.return_value = None

        result = search_tool.web_search.invoke({"query": "SBI fixed deposit rates"})

        self.assertIn("URL: https://sbi.co.in/web/interest-rates/deposit-rates", result)
        self.assertIn("Status: Unverified", result)


if __name__ == "__main__":
    unittest.main()
