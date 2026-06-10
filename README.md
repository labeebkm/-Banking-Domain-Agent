# Banking Domain Agent

A command-line banking assistant that only answers banking and finance questions.
It uses a fast keyword-based domain guard, local banking knowledge as deterministic
context, and Groq's LLaMA model through LangChain for final response generation.

## Project Overview

The assistant is designed to:

- reject off-topic questions before calling the LLM
- answer common banking questions about rates, products, regulations, and digital payments
- provide local context to the model instead of relying only on model memory
- avoid fragile LLM tool-calling behavior by selecting local context in Python

## Project Structure

```text
.
|-- agent.py                  # Thin CLI entry point for backward compatibility
|-- banking_agent/
|   |-- __init__.py
|   |-- cli.py                # Interactive command-line loop
|   |-- config.py             # Environment and model configuration
|   |-- context.py            # Selects relevant local knowledge for each question
|   |-- guard.py              # Banking-domain keyword guard
|   |-- knowledge.py          # Local banking knowledge providers
|   |-- prompts.py            # System prompt and standard responses
|   `-- service.py            # Core build/run assistant functions
|-- requirements.txt
|-- .env.example
`-- .gitignore
```

## Dependencies

- Python 3.11+
- `langchain-groq`
- `python-dotenv`

The installed environment may also include LangChain-related transitive packages.

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

Create your local environment file:

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

Start the interactive assistant:

```powershell
python agent.py
```

Or run it with the virtual environment Python directly:

```powershell
.\venv\Scripts\python.exe agent.py
```

Example:

```text
You: What is the current repo rate set by RBI?

Agent: The current repo rate set by the RBI is 5.25% as of the June 5, 2026,
Monetary Policy Committee decision. Please verify the latest rate at rbi.org.in
because policy rates can change.
```

Off-topic questions are rejected without calling the LLM:

```text
You: Tell me a recipe for biryani

Agent: I'm a banking-specialized assistant and can only help with banking and
finance topics. Please ask me something related to banking, loans, accounts,
payments, or financial regulations.
```

## How It Works

1. `guard.py` checks whether the user question is banking or finance related.
2. `context.py` selects relevant local banking knowledge from `knowledge.py`.
3. `service.py` sends the system prompt, selected context, and user question to Groq.
4. `cli.py` prints the response in an interactive terminal loop.

## Extending The Agent

To add a new knowledge area:

1. Add a new dictionary and lookup function in `banking_agent/knowledge.py`.
2. Add routing keywords for that area in `banking_agent/context.py`.
3. Add domain keywords in `banking_agent/guard.py` if the topic should pass the guard.
4. Update this README if the new feature changes setup or usage.

## Notes

- `.env` is intentionally ignored by git because it contains secrets.
- Current rates and regulations can change. The assistant includes known local context,
  but users should verify time-sensitive banking data with official sources.
