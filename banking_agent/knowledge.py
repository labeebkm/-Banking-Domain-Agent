"""Local banking knowledge providers used as deterministic context."""

INTEREST_RATES = {
    "savings": (
        "Typical savings account APY: 0.01% to 5.25% for high-yield accounts. "
        "As of mid-2025, top online banks offer about 4.5% to 5.0% APY."
    ),
    "fixed deposit": (
        "FD rates in India: about 6.5% to 8.0% p.a. for common 1-3 year tenures. "
        "Some small finance banks may offer higher rates."
    ),
    "home loan": (
        "Home loan rates in India: about 8.35% to 9.75% p.a. for floating-rate loans, "
        "depending on lender, credit profile, and tenure."
    ),
    "personal loan": "Personal loan rates: about 10.5% to 24% p.a. depending on credit score.",
    "car loan": "Car loan rates: about 8.5% to 15% p.a. depending on lender and tenure.",
}

BANKING_PRODUCTS = {
    "current account": (
        "Current accounts are for businesses and high-frequency transactions. "
        "They usually do not pay interest and may offer overdraft facilities."
    ),
    "savings account": (
        "Savings accounts are intended for individuals and usually include debit card, "
        "net banking, UPI, and interest on balances."
    ),
    "credit card": (
        "Credit cards offer revolving credit. Key terms include credit limit, APR, "
        "billing cycle, grace period, rewards, fees, and repayment due date."
    ),
    "demat account": (
        "A demat account holds securities electronically and is linked to trading "
        "activity through NSDL or CDSL depositories in India."
    ),
    "nri account": (
        "NRI account types include NRE, NRO, and FCNR accounts, each with different "
        "taxation, currency, and repatriation rules."
    ),
    "secured loan": (
        "A secured loan is backed by collateral such as property, a vehicle, deposits, "
        "or other assets. Because lender risk is lower, secured loans usually have "
        "lower interest rates, higher borrowing limits, and longer tenures, but the "
        "collateral can be repossessed on default."
    ),
    "unsecured loan": (
        "An unsecured loan does not require collateral. Approval depends more on income, "
        "credit score, and repayment history. These loans are usually faster to obtain, "
        "but they often carry higher interest rates, smaller limits, and shorter tenures."
    ),
    "secured and unsecured loans": (
        "Secured loans require collateral and usually offer lower rates and higher limits, "
        "while unsecured loans do not require collateral but typically have higher rates "
        "and stricter credit-based approval."
    ),
    "advantages and disadvantages of home loans": (
        "Advantages of home loans include spreading the cost of a property over a long tenure, "
        "possible tax benefits where applicable, and access to a large loan amount at relatively "
        "lower rates than many unsecured loans. Disadvantages include long repayment commitments, "
        "interest cost over time, processing and legal charges, and the risk of losing the property "
        "if repayments are not maintained."
    ),
    "salaried person": (
        "Suitable banking products for a salaried person often include a salary or savings account, "
        "an emergency fixed or recurring deposit, a credit card used with disciplined repayment, "
        "net banking and UPI services, and needs-based loans such as home, vehicle, or personal loans "
        "chosen according to repayment capacity."
    ),
    "loan": "Loan types include home, personal, car, education, gold, business, and loan against property.",
}

REGULATIONS = {
    "repo rate": (
        "RBI policy repo rate: 5.25% as of the June 5, 2026 Monetary Policy Committee decision. "
        "The repo rate is the rate at which RBI lends short-term funds to commercial banks. "
        "Rate changes influence lending rates, EMIs, deposit rates, liquidity, and inflation control. "
        "Always verify current policy rates at rbi.org.in because MPC decisions can change this rate."
    ),
    "repo": (
        "RBI policy repo rate: 5.25% as of the June 5, 2026 Monetary Policy Committee decision. "
        "The repo rate is the rate at which RBI lends short-term funds to commercial banks. "
        "Rate changes influence lending rates, EMIs, deposit rates, liquidity, and inflation control. "
        "Always verify current policy rates at rbi.org.in because MPC decisions can change this rate."
    ),
    "reverse repo": (
        "Reverse repo is the rate at which RBI absorbs surplus liquidity from banks. "
        "It works in the opposite direction of the repo rate and is used as a liquidity management tool."
    ),
    "rbi": (
        "Reserve Bank of India (RBI) is India's central bank and primary banking regulator. "
        "Key functions include monetary policy, bank licensing, forex management, and consumer protection."
    ),
    "basel": (
        "Basel III norms require banks to maintain minimum capital and liquidity standards, "
        "including CET1, Tier 1 capital, total capital, and buffer requirements."
    ),
    "kyc": (
        "KYC means Know Your Customer. It is mandatory identity verification for account opening, "
        "large transactions, and loan applications."
    ),
    "fdic": (
        "FDIC insures eligible deposits in the USA. India's equivalent deposit insurance is DICGC, "
        "which covers eligible deposits up to the applicable limit per depositor per bank."
    ),
    "dicgc": (
        "DICGC provides deposit insurance in India for eligible bank deposits up to the applicable "
        "insured limit per depositor per bank."
    ),
    "npa": (
        "NPA means Non-Performing Asset. In India, a loan is generally classified as NPA when "
        "principal or interest is overdue for more than 90 days."
    ),
    "ifrs": (
        "IFRS 9 requires banks to use an Expected Credit Loss model for financial asset impairment."
    ),
    "inflation": (
        "Inflation often pushes central banks to tighten monetary policy, which can lead to higher "
        "policy rates and, in turn, higher bank lending and deposit rates. When inflation eases, "
        "policy rates may stabilize or fall, which can reduce borrowing costs and eventually affect "
        "deposit returns as well."
    ),
}

TECHNOLOGY = {
    "upi": (
        "UPI is a real-time interbank payment system by NPCI that enables instant transfers "
        "using identifiers such as UPI IDs."
    ),
    "core banking": (
        "Core Banking Solution (CBS) connects branches to a central system and enables "
        "any-branch banking."
    ),
    "neft": (
        "NEFT is a batch-based funds transfer system in India and is available 24x7."
    ),
    "rtgs": (
        "RTGS is a real-time gross settlement system for high-value transactions in India."
    ),
    "swift": (
        "SWIFT is a global interbank messaging network used for international banking instructions."
    ),
    "open banking": (
        "Open banking uses secure APIs to let authorized third parties access bank data with consent."
    ),
}


def _lookup(query: str, data: dict[str, str], fallback: str) -> str:
    query_lower = query.lower()
    for key, value in data.items():
        if key in query_lower:
            return value
    return fallback

