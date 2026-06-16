# Banking Domain Agent

A command-line banking and finance assistant built with Python, LangGraph,
LangChain, Groq, and a small crawler-backed live-search pipeline.

The application rejects off-topic questions, answers common banking topics from
local deterministic knowledge, and routes time-sensitive questions to a search
pipeline that discovers and crawls banking sources without requiring a paid
search API.

## What The Project Does

- Limits responses to banking and finance topics with a keyword-based guard.
- Answers common product, regulation, rate, and payment-system questions from
  local dictionaries.
- Routes latest, current, recent, year-specific, and bank-specific questions to
  live search before invoking the router LLM.
- Uses a LangGraph ReAct router for banking questions that do not match a direct
  deterministic route.
- Extends the router with a local MCP server for loan eligibility, FD maturity,
  and loan-option comparison calculators.
- Rewrites live-search questions with Groq, discovers candidate pages through
  DuckDuckGo HTML, crawls useful pages, and summarizes supported snippets.
- Returns at most three source URLs and preserves official bank URLs for manual
  verification when their JavaScript-rendered content cannot be extracted.
- Handles Groq rate limits, malformed tool-call output, empty search results,
  and uncertain RBI repo-rate snippets with explicit fallback messages.

This is an educational assistant, not financial advice. Rates, eligibility,
regulations, and product terms can change; verify important details on the
official bank or regulator website before acting.

## Project Structure

```text
.
|-- agent.py                  # Compatibility entry point for the CLI
|-- banking_agent/
|   |-- __init__.py           # Public package exports
|   |-- cli.py                # Interactive terminal loop
|   |-- config.py             # Environment and Groq model settings
|   |-- guard.py              # Keyword-based banking-domain guard
|   |-- knowledge.py          # Local deterministic banking knowledge
|   |-- prompts.py            # Router and search-query prompts
|   |-- router_agent.py       # Direct routing and LangGraph ReAct router
|   |-- search_agent.py       # Query rewrite, crawler execution, summarization
|   |-- search_tool.py        # URL discovery, crawling, filtering, formatting
|   |-- service.py            # Public build/run service functions
|   `-- tools.py              # LangChain tools over local knowledge
|-- mcp_server/
|   |-- __init__.py
|   |-- calculators.py        # Pure loan and FD calculator logic
|   `-- server.py             # FastMCP stdio server
|-- MCP_USAGE.md              # MCP architecture and usage notes
|-- test_search_tool.py       # Crawler regression tests
|-- test_mcp_calculators.py   # MCP calculator regression tests
|-- test_two_agent.py         # Manual end-to-end smoke script
|-- requirements.txt
|-- .env.example
`-- .gitignore
```

## Request Flow

```text
User input
    |
    v
Banking-domain guard
    |-- off topic ------------------------> standard rejection
    |
    v
Live-search heuristic
    |-- latest/current/recent/bank detail -> search pipeline
    |
    v
Local-tool heuristic
    |-- known topic ----------------------> deterministic local answer
    |
    v
LangGraph ReAct router
    |-- local knowledge tool -------------> local answer
    |-- MCP calculator tool --------------> loan/FD calculation
    `-- delegate_to_search_agent ---------> search pipeline
```

The direct routing shortcuts reduce Groq usage for obvious questions. The
LangGraph router is used only after the domain guard, live-search heuristic,
and local-tool heuristic have not produced an answer.

### Local Route

The router can use these tools:

| Tool | Topics |
| --- | --- |
| `get_interest_rates` | Savings, fixed deposits, home loans, personal loans, car loans |
| `get_banking_products` | Accounts, cards, loans, demat accounts, NRI accounts |
| `get_regulatory_info` | RBI, repo rate, Basel III, KYC, DICGC, FDIC, NPA, IFRS |
| `get_banking_technology` | UPI, NEFT, RTGS, SWIFT, core banking, open banking |
| `delegate_to_search_agent` | Current or bank-specific information requiring live search |
| `check_loan_eligibility` | EMI, FOIR/DTI, affordability, and eligibility estimates |
| `calculate_fd_maturity` | Fixed-deposit maturity and interest earned |
| `compare_loan_options` | EMI, interest, total payment, and best loan option |

Local values live in `banking_agent/knowledge.py`. They are deterministic and
may be illustrative or time-sensitive, so they should not be treated as a
substitute for an official source.

### Live-Search Route

`banking_agent/search_agent.py` implements the search workflow directly; it is
not a second LangGraph graph. Its steps are:

1. Rewrite the user's question into a short crawler query with Groq. If query
   rewriting fails, append `official latest banking` to the original question.
2. Invoke the `web_search` LangChain tool.
3. Build up to eight candidate URLs using:
   - stable RBI pages for RBI-related queries;
   - known crawlable Groww pages for selected SBI, HDFC, ICICI, and Axis Bank
     fixed-deposit queries;
   - dynamic DuckDuckGo HTML results for other bank and product pages;
   - official bank homepages as citation-only fallbacks.
4. Remove duplicate and low-quality URLs, then prioritize official domains,
   recognized aggregators, and other results in that order.
5. Crawl HTML with `requests` and parse it with Beautiful Soup. Navigation,
   scripts, headers, footers, cookie text, and similar boilerplate are removed.
6. Select compact query-relevant snippets. Rate queries require numeric rate
   evidence; document and eligibility queries require matching content.
7. Summarize at most 3,000 characters of crawler output with Groq and force the
   final source list to use only URLs returned by the crawler.

The crawler returns at most three successful results. Official URLs that fail
to yield useful HTML are marked internally as unverified and can still be shown
so the user has an authoritative page to inspect manually.

## Requirements

- Python 3.11 or newer
- A Groq API key
- Network access for Groq, DuckDuckGo HTML, and target banking websites

Python packages are declared in `requirements.txt`:

- `langchain-core`
- `langchain-groq`
- `langgraph`
- `python-dotenv`
- `requests`
- `beautifulsoup4`
- `mcp`
- `langchain-mcp-adapters`

## Setup

Create and activate a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create the local environment file:

```powershell
Copy-Item .env.example .env
```

Set your Groq API key in `.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant
MODEL_TEMPERATURE=0.2
DEBUG_AGENTS=1
```

`GROQ_MODEL`, `MODEL_TEMPERATURE`, and `DEBUG_AGENTS` are optional. Debug output
is enabled by default; use `DEBUG_AGENTS=0` to hide routing and crawler messages.

## Usage

Start the interactive assistant:

```powershell
python agent.py
```

The package CLI is equivalent:

```powershell
python -m banking_agent.cli
```

Enter `exit` or `quit` to stop.

Example questions:

```text
What is KYC?
How does UPI work?
What is a demat account?
What are the latest SBI home loan rates?
What are the latest RBI announcements?
```

An off-topic question returns the standard banking-only response without
calling Groq for an answer.

## Programmatic Use

```python
from banking_agent import build_two_agent_system, run_two_agent_system

agent = build_two_agent_system()
answer = run_two_agent_system(agent, "What is KYC?")
print(answer)
```

Despite the compatibility name `build_two_agent_system`, the returned object is
a router wrapper containing the LangGraph router and the merged local/Search/MCP
tool registry. Search is delegated to the procedural workflow in
`search_agent.py`.

For async contexts, use `build_two_agent_system_async()` so MCP tools can be
loaded without blocking an already-running event loop.

## Testing

Run the crawler regression suite:

```powershell
python -m unittest -v test_search_tool.py
```

Run the MCP calculator regression suite:

```powershell
python -m unittest -v test_mcp_calculators.py
```

Run the manual smoke script, which requires a valid Groq key and network access:

```powershell
python test_two_agent.py
```

The smoke script checks a local KYC question, an SBI live-rate question, an RBI
announcement question, and an off-topic question.

At the current repository snapshot, all Python files compile, but
`test_search_tool.py` is partially out of sync with the crawler implementation:
four of its seven tests fail because they expect removed helpers, older table
formatting, and an older unverified-source format. The application code and
tests should be reconciled before treating that suite as a passing CI gate.

## Configuration And Routing Notes

- `GROQ_API_KEY` is loaded from `.env` with `python-dotenv`.
- The default model is `llama-3.1-8b-instant` with temperature `0.2`.
- Live-search triggers include words such as `latest`, `current`, `today`,
  `recent`, `live`, `offer`, `2025`, and `2026`.
- Bank-specific loan, rate, interest, product, account, card, RBI, or repo
  questions are also routed directly to search.
- The domain guard is keyword-based, not a semantic classifier. A special check
  rejects common `capital of ...` questions that would otherwise match the
  ambiguous banking keyword `capital`.
- Search output is converted to ASCII for compatibility with the Windows
  console, so non-ASCII characters may be removed.
- The crawler uses six-second connection and fifteen-second read timeouts.
- No Tavily, SerpAPI, Google Custom Search, or other paid search key is used.

## Troubleshooting

- **Groq authentication errors:** confirm `GROQ_API_KEY` is present in `.env`
  and that the same Python environment is running the application.
- **Rate-limit messages:** wait and retry, or verify the information directly
  with the official bank or regulator.
- **No useful live results:** DuckDuckGo or the target site may be unavailable,
  blocked, JavaScript-rendered, or missing query-relevant content.
- **Imports fail:** activate the project virtual environment and reinstall
  `requirements.txt` with that environment's Python executable.
- **PowerShell activation is blocked:** run commands directly with
  `.\venv\Scripts\python.exe`.

## Extending The Project

To add deterministic banking knowledge:

1. Add data and lookup behavior in `banking_agent/knowledge.py`.
2. Add or update a LangChain tool in `banking_agent/tools.py`.
3. Include new tools in `BANKING_TOOLS`.
4. Update guard and direct-routing keywords when needed.
5. Update the router prompt and tests.

To extend live search, update source classification, candidate discovery,
snippet validation, or result formatting in `banking_agent/search_tool.py`, then
keep URL extraction and summary behavior in `banking_agent/search_agent.py`
compatible with the crawler output.
