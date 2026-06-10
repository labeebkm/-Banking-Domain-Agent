"""LangChain tools backed by local banking knowledge."""

from langchain_core.tools import tool

from banking_agent.knowledge import (
    BANKING_PRODUCTS,
    INTEREST_RATES,
    REGULATIONS,
    TECHNOLOGY,
    _lookup,
)


@tool
def get_interest_rates(query: str) -> str:
    """Use this for banking interest-rate questions, including savings rates, fixed deposits, repo-linked rates, home loans, personal loans, and car loans."""
    return _lookup(
        query,
        INTEREST_RATES,
        "Common interest-rate topics include savings rates, fixed deposits, home loans, personal loans, and car loans.",
    )


@tool
def get_banking_products(query: str) -> str:
    """Use this for questions about banking products or services, including accounts, cards, loans, demat accounts, and NRI accounts."""
    return _lookup(
        query,
        BANKING_PRODUCTS,
        "Major banking products include savings accounts, current accounts, FD/RD, cards, loans, demat accounts, and NRI accounts.",
    )


@tool
def get_regulatory_info(query: str) -> str:
    """Use this for banking regulation and compliance questions, including RBI, repo rate, Basel III, KYC, DICGC, NPA, FDIC, and IFRS topics."""
    return _lookup(
        query,
        REGULATIONS,
        "Key banking regulations include RBI guidelines, Basel III, KYC/AML, DICGC insurance, and NPA classification norms.",
    )


@tool
def get_banking_technology(query: str) -> str:
    """Use this for banking technology and payment-system questions, including UPI, NEFT, RTGS, SWIFT, core banking, and open banking."""
    return _lookup(
        query,
        TECHNOLOGY,
        "Banking technology topics include UPI, NEFT, RTGS, IMPS, SWIFT, CBS, open banking, digital KYC, and CBDC.",
    )


BANKING_TOOLS = [
    get_interest_rates,
    get_banking_products,
    get_regulatory_info,
    get_banking_technology,
]
