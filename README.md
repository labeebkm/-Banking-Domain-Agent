# Banking Domain Agent

A command-line banking assistant that only answers banking and finance questions.
The project uses a domain guard, a LangGraph ReAct router agent, local banking
knowledge tools, a Tavily-backed web-search tool, and Groq's LLaMA model for
response generation.

## Project Overview

The assistant is built to:

- reject off-topic questions before calling the LLM
- use local banking tools for rates, products, regulations, and payment technology
- use Tavily web search for current rates, latest RBI updates, and recent banking news
- keep banking knowledge in maintainable modules instead of one large script
- recover from malformed Groq tool-call output when the requested tool and arguments can be parsed
- remind users to verify time-sensitive rates and regulations with official sources

## Project Structure

```text
.
|-- agent.py                  # Thin CLI launcher
|-- banking_agent/
|   |-- __init__.py
|   |-- cli.py                # Interactive command-line loop
|   |-- config.py             # Environment and model configuration
|   |-- guard.py              # Banking-domain keyword guard
|   |-- knowledge.py          # Local banking knowledge dictionaries and lookup helpers
|   |-- prompts.py            # System prompt and standard responses
|   |-- router_agent.py       # Router agent with local tools and live search
|   |-- search_agent.py       # Dedicated web-search agent
|   |-- search_tool.py        # Tavily search tool
|   |-- service.py            # Agent construction, execution, and tool-call recovery
|   `-- tools.py              # LangChain tools backed by local banking knowledge
|-- requirements.txt
|-- test_two_agent.py
|-- .env.example
`-- .gitignore
```

## Architecture

```text
User question
    |
    v
Domain guard
    |
    |-- off-topic --> standard rejection response
    |
    v
LangGraph ReAct router agent
    |
    |-- general banking concepts --> local banking tools
    |-- current/latest/recent data --> Tavily web_search tool
    |
    v
Tools
    |
    |-- get_interest_rates
    |-- get_banking_products
    |-- get_regulatory_info
    |-- get_banking_technology
    `-- web_search
    |
    v
Final banking response
```

If Groq returns a malformed tool-call message but the tool name and JSON arguments
can still be parsed, `service.py` recovers by invoking the matching local tool
directly and returning a useful banking response.

## Dependencies

The main dependencies are listed in `requirements.txt`:

- Python 3.11+
- `langchain-core`
- `langchain-community`
- `langchain-groq`
- `langgraph`
- `python-dotenv`
- `tavily-python`

## Setup

Create and activate a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create a local environment file:

```powershell
copy .env.example .env
```

Edit `.env` and add your API keys:

```env
GROQ_API_KEY=your_groq_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
```

Optional model settings:

```env
GROQ_MODEL=llama-3.3-70b-versatile
MODEL_TEMPERATURE=0.2
```

## Usage

Start the assistant:

```powershell
python agent.py
```

If you want to force the project virtual environment Python:

```powershell
.\venv\Scripts\python.exe agent.py
```

You can also run the package module directly:

```powershell
python -m banking_agent.cli
```

Example banking question:

```text
You: What is the current repo rate set by RBI?

Agent: According to the local banking knowledge tool, the RBI policy repo rate
is 5.25% as of the June 5, 2026 Monetary Policy Committee decision. Please
verify current policy rates at rbi.org.in because MPC decisions can change.
```

Example off-topic question:

```text
You: Tell me a recipe for biryani

Agent: I'm a banking-specialized assistant and can only help with banking and
finance topics. Please ask me something related to banking, loans, accounts,
payments, or financial regulations.
```

## Available Tools

| Tool | Purpose |
| --- | --- |
| `get_interest_rates` | Savings rates, fixed deposits, repo-linked rates, home loans, personal loans, car loans |
| `get_banking_products` | Accounts, cards, loans, demat accounts, NRI accounts, banking products |
| `get_regulatory_info` | RBI, repo rate, Basel III, KYC, DICGC, FDIC, NPA, IFRS, regulations |
| `get_banking_technology` | UPI, NEFT, RTGS, SWIFT, core banking, open banking, payment systems |
| `web_search` | Live banking data, current loan rates, latest RBI announcements, recent financial news |

## How It Works

1. `guard.py` checks whether the question is banking or finance related.
2. `service.py` builds the two-agent system through `build_two_agent_system()`.
3. `router_agent.py` decides whether to use local banking tools or `web_search`.
4. `search_agent.py` provides a dedicated Tavily-only search agent for live data use cases.
5. `knowledge.py` provides deterministic local answers for local tools.
6. `service.py` keeps the older `build_agent()` and `run_agent()` functions for backward compatibility.
7. `cli.py` manages the terminal chat loop and uses the two-agent system by default.

## Extending The Agent

To add a new banking knowledge area:

1. Add local data and lookup logic in `banking_agent/knowledge.py`.
2. Add a LangChain tool in `banking_agent/tools.py`.
3. Add the new tool to `BANKING_TOOLS`.
4. Add any needed keywords in `banking_agent/guard.py`.
5. Update `SYSTEM_PROMPT` in `banking_agent/prompts.py` so the agent knows when to use the new tool.
6. Update this README with the new tool and usage notes.

## Manual Test Script

Run the two-agent smoke test:

```powershell
python test_two_agent.py
```

The script checks:

- local knowledge question: `What is KYC?`
- live search question: `What are the latest home loan rates from SBI?`
- recent news question: `What are the latest RBI announcements?`
- off-topic question: `What is the capital of France?`

## Notes

- `.env` is ignored by git and should not be committed.
- `agent.py` is intentionally small; the implementation lives inside the `banking_agent/` package.
- Time-sensitive banking data can change. Verify current rates, rules, and regulations against official sources.
- Live search requires a valid `TAVILY_API_KEY`.

## Troubleshooting

- If imports fail, make sure dependencies are installed with `pip install -r requirements.txt`.
- If Groq calls fail, confirm `GROQ_API_KEY` is set correctly in `.env`.
- If live search fails, confirm `TAVILY_API_KEY` is set correctly in `.env`.
- If PowerShell cannot activate the virtual environment, run commands with `.\venv\Scripts\python.exe` directly.
