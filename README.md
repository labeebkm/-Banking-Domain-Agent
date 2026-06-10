# Banking Domain Agent — LangChain

A domain-restricted conversational agent that **only** answers banking and finance questions.
Built with LangChain's ReAct agent framework and Groq (LLaMA 3.3 70B) as the LLM backend.

---

## Architecture

```
User Input
    │
    ▼
┌─────────────────────┐
│  Layer 1: Keyword   │  ← Fast pre-filter (no LLM cost for off-topic)
│  Domain Guard       │
└────────┬────────────┘
         │ (banking-related only)
         ▼
┌─────────────────────┐
│  ReAct Agent        │  ← LangChain AgentExecutor
│  (LLaMA 3.3 70B     │     Thought → Action → Observation loop
│   via Groq)         │
└────────┬────────────┘
         │
    ┌────┴──────────────────────────────┐
    │           TOOLS                   │
    ├───────────────────────────────────┤
    │ InterestRates     BankingProducts │
    │ BankingRegulations BankingTech    │
    └───────────────────────────────────┘
         │
         ▼
    Final Answer
```

## Domain Restriction — Two-Layer Approach

| Layer | Method | Purpose |
|-------|--------|---------|
| 1 | Keyword filter (`is_banking_related()`) | Blocks off-topic queries before hitting the LLM — saves cost & latency |
| 2 | System prompt instruction | LLM-level enforcement for edge cases that pass Layer 1 |

## Tools

| Tool | Covers |
|------|--------|
| `InterestRates` | Savings, FD, home/personal/car loan rates |
| `BankingProducts` | Account types, credit cards, demat, NRI accounts |
| `BankingRegulations` | RBI, Basel III, KYC, DICGC, NPA, IFRS 9 |
| `BankingTechnology` | UPI, NEFT, RTGS, SWIFT, CBS, Open Banking |

## Setup

```bash
# 1. Clone / copy the files
# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your API key
cp .env.example .env
# Edit .env and add your GROQ_API_KEY (free at console.groq.com)

# 4. Run
python agent.py
```

## Example Interaction

```
You: What is the current repo rate set by RBI?

Agent: The RBI (Reserve Bank of India) uses the repo rate as its key
monetary policy tool. As of 2025, the repo rate stands at 6.50%.
It influences lending rates across all banks in India.

---

You: Tell me a recipe for biryani

Agent: I'm a banking-specialized assistant and can only help with
banking and finance topics. Please ask me something related to
banking, loans, accounts, payments, or financial regulations.
```

## Extending the Agent

To add new knowledge areas, create a new function and register it as a `Tool`:

```python
def get_trade_finance(query: str) -> str:
    # Your logic here
    return "Trade finance info..."

Tool(
    name="TradeFinance",
    func=get_trade_finance,
    description="Use for questions about LC, export credit, forfaiting, etc."
)
```
