# Problem 5 — Build the agent team and grow the MCP tools

This section contains the PydanticAI team, typed data models, role prompts, and the runner that coordinates tickets through the Campus Customs MCP server.
The team gets all shop data from the project's `data/campus_customs_new.db` through the MCP server.

## Files

- `backend/prompts/`: one role prompt per agent.
- `backend/models.py`: validated assignment, work, and resolution types.
- `backend/`: PydanticAI agent definitions, MCP connection setup, audit persistence, and the command-line runner.
- `../output/audit_trail.json`: append-preserved audit events. It records run and dispatch metadata, not customer identifiers, financial details, or full model/tool content.

## Run

From the HW 5 project root, install the dependencies, configure `PYDANTIC_AI_MODEL` and the corresponding provider credentials, then run the agent team:

```powershell
Push-Location "Problem 5 - Build the agent team and grow the MCP tools"
python -m pip install -r "backend\requirements.txt"
$env:PYDANTIC_AI_MODEL = "openai:gpt-4o-mini"
python -m backend.main
Pop-Location
```

To process one ticket, pass its ID:

```powershell
Push-Location "Problem 5 - Build the agent team and grow the MCP tools"
python -m backend.main --ticket-id 101
Pop-Location
```

Ticket reads and business-data actions go through the MCP server. Purchase-order drafts are informational only; the server does not place orders, issue payments, or change ticket records.
