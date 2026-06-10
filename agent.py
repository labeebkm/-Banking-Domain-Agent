"""
Banking Domain Agent - LangChain Implementation
================================================
A domain-restricted agent that ONLY answers banking-related questions.
Off-topic queries are gracefully rejected.

Author  : Labeeb KM
Stack   : LangChain · Groq (LLaMA 3.3 70B) · Python 3.12
"""

import os
from typing import Any

from dotenv import load_dotenv

from langchain_groq import ChatGroq

load_dotenv()


# ──────────────────────────────────────────────
# 1. TOOLS  (domain-specific knowledge tools)
# ──────────────────────────────────────────────

def get_interest_rates(query: str) -> str:
    """Returns common banking interest rate information."""
    rates_db = {
        "savings": "Typical savings account APY: 0.01% – 5.25% (high-yield). "
                   "As of mid-2025, top online banks offer 4.5–5.0% APY.",
        "fixed deposit": "FD rates in India (2025): 6.5% – 8.0% p.a. for 1–3 year tenures. "
                         "Small finance banks offer up to 9.0%.",
        "home loan": "Home loan rates (India, 2025): 8.35% – 9.75% p.a. (floating). "
                     "SBI offers from 8.50%, HDFC from 8.75%.",
        "personal loan": "Personal loan rates: 10.5% – 24% p.a. depending on credit score.",
        "car loan": "Car loan rates: 8.5% – 15% p.a. depending on lender and tenure.",
    }
    query_lower = query.lower()
    for key, value in rates_db.items():
        if key in query_lower:
            return value
    return ("Common interest rates: Savings (4–5% APY), FD (6.5–8%), "
            "Home Loan (8.35–9.75%), Personal Loan (10.5–24%), Car Loan (8.5–15%).")


def get_banking_products(query: str) -> str:
    """Returns information about banking products and services."""
    products = {
        "current account": "Current accounts are for businesses/high-frequency transactions. "
                           "No interest paid; offers overdraft facilities. "
                           "Minimum balance: ₹5,000–₹25,000 typically.",
        "savings account": "Savings accounts earn interest (2.5–4% in India). "
                           "Ideal for individuals. Features: debit card, net banking, UPI.",
        "credit card": "Credit cards offer revolving credit. Key metrics: credit limit, "
                       "APR (15–42%), billing cycle (30 days), grace period (20–45 days). "
                       "Types: rewards, cashback, travel, secured.",
        "demat account": "Demat account holds securities electronically. "
                         "Required for stock market investing. Linked to trading account. "
                         "Maintained by NSDL/CDSL depositories.",
        "nri account": "NRI accounts: NRE (tax-free, repatriable), NRO (taxable, limited repatriation), "
                       "FCNR (foreign currency, fixed deposit).",
        "loan": "Loan types: Home, Personal, Car, Education, Gold, Business, Loan against property.",
    }
    query_lower = query.lower()
    for key, value in products.items():
        if key in query_lower:
            return value
    return ("Major banking products: Savings Account, Current Account, FD/RD, "
            "Credit Card, Debit Card, Home/Personal/Car Loans, Demat Account, "
            "NRI Accounts, Insurance-linked products.")


def get_regulatory_info(query: str) -> str:
    """Returns banking regulatory and compliance information."""
    regulations = {
        "repo rate": "RBI policy repo rate: 5.25% as of the June 5, 2026 Monetary Policy Committee decision. "
                     "The repo rate is the rate at which RBI lends short-term funds to commercial banks. "
                     "Rate changes influence lending rates, EMIs, deposit rates, liquidity, and inflation control. "
                     "Always verify current policy rates at rbi.org.in because MPC decisions can change this rate.",
        "repo": "RBI policy repo rate: 5.25% as of the June 5, 2026 Monetary Policy Committee decision. "
                "The repo rate is the rate at which RBI lends short-term funds to commercial banks. "
                "Rate changes influence lending rates, EMIs, deposit rates, liquidity, and inflation control. "
                "Always verify current policy rates at rbi.org.in because MPC decisions can change this rate.",
        "reverse repo": "Reverse repo is the rate at which RBI absorbs surplus liquidity from banks. "
                        "It works in the opposite direction of the repo rate and is used as a liquidity management tool.",
        "rbi": "Reserve Bank of India (RBI) is India's central bank and primary banking regulator. "
               "Key functions: monetary policy, bank licensing, FOREX management, consumer protection.",
        "basel": "Basel III norms require banks to maintain: CET1 ratio ≥ 4.5%, "
                 "Tier 1 capital ≥ 6%, Total Capital ratio ≥ 8%, plus a 2.5% capital conservation buffer.",
        "kyc": "KYC (Know Your Customer): mandatory identity verification. "
               "Documents: Aadhaar, PAN, Passport, Voter ID. "
               "Required for account opening, large transactions, loan applications.",
        "fdic": "FDIC (USA) insures deposits up to $250,000 per depositor per bank. "
                "India equivalent: DICGC covers up to ₹5 lakh per depositor per bank.",
        "npa": "NPA (Non-Performing Asset): loan where principal/interest is overdue > 90 days. "
               "Sub-categories: Sub-standard, Doubtful, Loss assets.",
        "ifrs": "IFRS 9 requires banks to use Expected Credit Loss (ECL) model "
                "for provisioning rather than the older incurred-loss approach.",
    }
    query_lower = query.lower()
    for key, value in regulations.items():
        if key in query_lower:
            return value
    return ("Key banking regulations: RBI guidelines, Basel III capital norms, "
            "KYC/AML compliance, DICGC deposit insurance (₹5L), NPA classification norms.")


def get_banking_technology(query: str) -> str:
    """Returns info about banking technology and digital finance."""
    tech_info = {
        "upi": "UPI (Unified Payments Interface): real-time interbank payment system by NPCI. "
               "Enables 24×7 instant transfers using VPA. Processed 13+ billion transactions/month in 2024.",
        "core banking": "Core Banking Solution (CBS): centralised system connecting all bank branches. "
                        "Enables any-branch banking. Common platforms: Finacle (Infosys), BaNCS (TCS), "
                        "Flexcube (Oracle).",
        "neft": "NEFT (National Electronic Funds Transfer): batch-based fund transfer. "
                "Available 24×7 (since Dec 2019). Settlement in half-hourly batches.",
        "rtgs": "RTGS (Real Time Gross Settlement): for high-value transactions (min ₹2 lakh). "
                "Real-time, individual settlement. Available 24×7.",
        "swift": "SWIFT: global interbank messaging network for international fund transfers. "
                 "Uses BIC codes. Settlement via correspondent banking.",
        "open banking": "Open Banking uses APIs to allow third-party fintechs to access bank data "
                        "(with customer consent). Enables PFM apps, credit scoring, account aggregation.",
    }
    query_lower = query.lower()
    for key, value in tech_info.items():
        if key in query_lower:
            return value
    return ("Banking technology topics: UPI, NEFT, RTGS, IMPS, SWIFT, Core Banking Systems (CBS), "
            "Open Banking APIs, Digital KYC, CBDC (Digital Rupee).")


# ──────────────────────────────────────────────
# 2. DOMAIN GUARD  (off-topic rejection filter)
# ──────────────────────────────────────────────

BANKING_KEYWORDS = {
    "bank", "banking", "loan", "credit", "debit", "mortgage", "interest", "rate",
    "deposit", "withdraw", "account", "savings", "investment", "finance", "financial",
    "atm", "transaction", "transfer", "payment", "kyc", "npa", "rbi", "fdic", "basel",
    "repo", "reverse repo",
    "neft", "rtgs", "upi", "imps", "swift", "cheque", "check", "emi", "fd", "rd",
    "mutual fund", "stock", "equity", "bond", "insurance", "forex", "currency",
    "inflation", "monetary", "central bank", "liquidity", "capital", "collateral",
    "overdraft", "lien", "pledge", "hypothecation", "securitization", "demat",
    "nri", "fdi", "nbfc", "microfinance", "fintech", "digital rupee", "cbdc",
    "core banking", "open banking", "credit score", "cibil", "repo rate", "crr", "slr",
}


def is_banking_related(question: str) -> bool:
    """Checks if a question is related to the banking domain."""
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in BANKING_KEYWORDS)


SYSTEM_PROMPT = """
You are a specialized Banking Domain Assistant. Your ONLY purpose is to answer questions
strictly related to banking, finance, and financial services.

STRICT RULES:
- You MUST only respond to banking/finance-related questions.
- If a question is NOT related to banking or finance, respond with:
  "I'm a banking-specialized assistant and can only help with banking and finance topics.
   Please ask me something related to banking, loans, accounts, payments, or financial regulations."
- Never attempt to answer questions outside the banking domain, even if you know the answer.
- Use the provided banking context when it is relevant.
- If the provided context contains an exact policy rate, answer with that rate first.
- Be professional, precise, and helpful within the banking domain.
- If the user asks for current rates or current regulations and the provided context may be outdated,
  clearly mention that they should verify against the latest official source.
"""


def get_banking_context(question: str) -> str:
    """Selects local banking knowledge to pass to the LLM as plain context."""
    question_lower = question.lower()
    context_parts = []

    if any(term in question_lower for term in ("rate", "interest", "repo", "loan", "fd", "deposit")):
        context_parts.append(f"Interest rate context: {get_interest_rates(question)}")
    if any(term in question_lower for term in ("account", "card", "demat", "nri", "product", "loan")):
        context_parts.append(f"Banking product context: {get_banking_products(question)}")
    if any(term in question_lower for term in ("rbi", "repo", "basel", "kyc", "fdic", "dicgc", "npa", "ifrs", "regulation")):
        context_parts.append(f"Regulatory context: {get_regulatory_info(question)}")
    if any(term in question_lower for term in ("upi", "neft", "rtgs", "swift", "core banking", "open banking", "cbdc")):
        context_parts.append(f"Banking technology context: {get_banking_technology(question)}")

    return "\n".join(context_parts) or "No local context matched. Answer from banking knowledge only."


# ──────────────────────────────────────────────
# 3. LLM + AGENT SETUP
# ──────────────────────────────────────────────

def build_agent() -> Any:
    """Builds and returns the banking domain agent."""

    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        api_key=os.getenv("GROQ_API_KEY"),
    )

    # ReAct prompt — strict domain restriction baked in


# ──────────────────────────────────────────────
# 4. MAIN  (interactive chat loop)
# ──────────────────────────────────────────────

def run_agent(agent: Any, user_input: str) -> str:
    """
    Runs the agent with a two-layer domain guard:
      Layer 1 — Keyword filter (fast, before hitting the LLM)
      Layer 2 — System-prompt instruction (LLM-level enforcement)
    """
    if not is_banking_related(user_input):
        return (
            "I'm a banking-specialized assistant and can only help with banking "
            "and finance topics. Please ask me something related to banking, loans, "
            "accounts, payments, or financial regulations."
        )

    banking_context = get_banking_context(user_input)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Banking context:\n{banking_context}\n\n"
                f"User question: {user_input}"
            ),
        },
    ]

    try:
        response = agent.invoke(messages)
    except Exception as exc:
        return (
            "I couldn't get a response from Groq right now. "
            f"Please check your API key/network and try again. Details: {exc}"
        )

    return getattr(response, "content", str(response))


def main():
    print("=" * 60)
    print("  Banking Domain Agent  (powered by LangChain + Groq)")
    print("  Type 'exit' or 'quit' to stop.")
    print("=" * 60)

    agent = build_agent()

    while True:
        user_input = input("\nYou: ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        print("\nAgent thinking...\n")
        response = run_agent(agent, user_input)
        print(f"\nAgent: {response}\n")
        print("-" * 60)


if __name__ == "__main__":
    main()
