# MCP Usage

## Architecture

The project now includes a local MCP server for deterministic banking
calculators:

```text
User Query
    |
    v
Router Agent
    |
    |-- Existing Local Tools
    |-- Search Agent delegation
    `-- MCP Tools from mcp_server/server.py
    |
    v
Final Response
```

The MCP server extends the existing tool set. It does not replace local banking
knowledge tools or the Search Agent.

## MCP Tools

- `check_loan_eligibility`: estimates EMI, FOIR/DTI ratio, maximum affordable
  EMI, eligibility status, and a reason.
- `calculate_fd_maturity`: calculates fixed-deposit maturity amount and
  interest earned using compound interest.
- `compare_loan_options`: compares loan options by EMI, total interest, total
  payment, and selects the lowest total-payment option.

All tools use pure Python logic from `mcp_server/calculators.py` and make no
external API calls.

## Installation

Create and activate the project virtual environment, then install dependencies:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The MCP dependencies are:

```text
mcp
langchain-mcp-adapters
```

## Stdio Launch

The MCP server is implemented with the official Python MCP SDK:

```python
from mcp.server.fastmcp import FastMCP
```

It runs with stdio transport when executed directly:

```powershell
python mcp_server/server.py
```

During normal agent startup, the Router Agent launches the server through
`langchain_mcp_adapters.client.MultiServerMCPClient` with this stdio
configuration:

```python
{
    "labeeb_banking_calculator": {
        "command": sys.executable,
        "args": ["mcp_server/server.py"],
        "transport": "stdio",
    }
}
```

## Agent Integration

`banking_agent/router_agent.py` loads MCP tools with:

```python
tools = await client.get_tools()
```

The loaded MCP tools are merged with the existing local tools and
`delegate_to_search_agent` before `llm.bind_tools(...)`.

The CLI remains synchronous:

```powershell
python agent.py
```

## Example Prompts

```text
Am I eligible for a 25 lakh home loan if my monthly income is 80000, existing obligations are 15000, annual rate is 8.5%, and tenure is 20 years?
```

```text
What will be the maturity amount for a 5 lakh FD at 7% for 5 years with quarterly compounding?
```

```text
Compare these loan options:
- 10 lakh at 8.5% for 20 years
- 10 lakh at 9.0% for 15 years
- 10 lakh at 8.75% for 18 years
```

## Notes

The calculator tools use a 50% FOIR threshold for loan eligibility. Results are
estimates for educational use and should be verified with the lender before any
financial decision.
