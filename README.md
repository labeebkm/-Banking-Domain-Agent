# Banking Domain Agent

A command-line banking assistant that only answers banking and finance questions.
The project uses a domain guard, LangGraph ReAct agent flow, LangChain tools backed
by local banking knowledge, and Groq's LLaMA model for response generation.

## Project Overview

The assistant is built to:

- reject off-topic questions before calling the LLM
- use banking-specific tools for rates, products, regulations, and payment technology
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
|   |-- service.py            # Agent construction, execution, and tool-call recovery
|   `-- tools.py              # LangChain tools backed by local banking knowledge
|-- requirements.txt
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
LangGraph ReAct agent
    |
    v
Banking tools
    |
    |-- get_interest_rates
    |-- get_banking_products
    |-- get_regulatory_info
    `-- get_banking_technology
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
- `langchain-groq`
- `langgraph`
- `python-dotenv`

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

Edit `.env` and add your Groq API key:

```env
GROQ_API_KEY=your_groq_api_key_here
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

## How It Works

1. `guard.py` checks whether the question is banking or finance related.
2. `service.py` builds a LangGraph ReAct agent using Groq and the tools from `tools.py`.
3. `prompts.py` instructs the agent to call the relevant tool before answering.
4. `knowledge.py` provides deterministic local answers for each tool.
5. `service.py` returns the final response or recovers from parseable malformed tool-call errors.
6. `cli.py` manages the terminal chat loop.

## Extending The Agent

To add a new banking knowledge area:

1. Add local data and lookup logic in `banking_agent/knowledge.py`.
2. Add a LangChain tool in `banking_agent/tools.py`.
3. Add the new tool to `BANKING_TOOLS`.
4. Add any needed keywords in `banking_agent/guard.py`.
5. Update `SYSTEM_PROMPT` in `banking_agent/prompts.py` so the agent knows when to use the new tool.
6. Update this README with the new tool and usage notes.

## Notes

- `.env` is ignored by git and should not be committed.
- `agent.py` is intentionally small; the implementation lives inside the `banking_agent/` package.
- Time-sensitive banking data can change. Verify current rates, rules, and regulations against official sources.

## Troubleshooting

- If imports fail, make sure dependencies are installed with `pip install -r requirements.txt`.
- If Groq calls fail, confirm `GROQ_API_KEY` is set correctly in `.env`.
- If PowerShell cannot activate the virtual environment, run commands with `.\venv\Scripts\python.exe` directly.
