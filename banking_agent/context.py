"""Context selection for banking questions."""

from banking_agent.knowledge import (
    get_banking_products,
    get_banking_technology,
    get_interest_rates,
    get_regulatory_info,
)


def get_banking_context(question: str) -> str:
    """Select local banking knowledge to pass to the LLM as plain context."""
    question_lower = question.lower()
    context_parts = []

    if any(term in question_lower for term in ("rate", "interest", "repo", "loan", "fd", "deposit")):
        context_parts.append(f"Interest rate context: {get_interest_rates(question)}")

    if any(term in question_lower for term in ("account", "card", "demat", "nri", "product", "loan")):
        context_parts.append(f"Banking product context: {get_banking_products(question)}")

    if any(
        term in question_lower
        for term in ("rbi", "repo", "basel", "kyc", "fdic", "dicgc", "npa", "ifrs", "regulation")
    ):
        context_parts.append(f"Regulatory context: {get_regulatory_info(question)}")

    if any(term in question_lower for term in ("upi", "neft", "rtgs", "swift", "core banking", "open banking", "cbdc")):
        context_parts.append(f"Banking technology context: {get_banking_technology(question)}")

    return "\n".join(context_parts) or "No local context matched. Answer from banking knowledge only."
