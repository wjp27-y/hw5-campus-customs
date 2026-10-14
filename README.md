# HW 5 â€” Campus Customs agentic team

HW 5 is a new assignment focused on creating an agentic team that runs the Campus Customs shop. Its supplied data archive, `data(2).zip`, contains `data/campus_customs.db`; the database is staged in `data/`.

## Problems

| Problem | Work |
|---|---|
| 1 â€” Vibe coder prompts | [Prompt log](Problem%201%20-%20Vibe%20coder%20prompts/AI_prompts.md) |
| 2 â€” Study the Campus Customs database | [Schema and study materials](Problem%202%20-%20Campus%20Customs%20study/) |
| 3 â€” Build the MCP server | [MCP server](Problem%203%20-%20Build%20the%20MCP%20server/mcp_server/) |
| 4 â€” Add the MCP server to the vibe coder and test each tool | [Problem 4 section](Problem%204%20-%20Add%20and%20test%20the%20MCP%20server/) |
| 5 â€” Build the agent team and grow the MCP tools | [PydanticAI agent team](Problem%205%20-%20Build%20the%20agent%20team%20and%20grow%20the%20MCP%20tools/) |
| 6 â€” Plan the three tickets | [Ticket planning page](output/desk_tickets.html) |
| 7 â€” Backend routes | [FastAPI backend](Problem%207%20-%20Backend%20routes/) |
| 8 - Agent dashboard | [React + Vite + TypeScript frontend](Problem%208%20-%20Agent%20dashboard/frontend/) |

The Campus Customs MCP server is configured in the project-root `.mcp.json`. Smoke-test results are saved in `output/mcp_smoke.json`.

## Running the submission

From the repository root, create a virtual environment, install the dependencies, and copy `.env.example` to `.env` with the required local credentials. Never commit `.env`.

Before running the agent team, reset the working database by copying the original database over it:

```powershell
Copy-Item data/campus_customs.db data/campus_customs_new.db -Force
```

Start the MCP server in one terminal:

```powershell
python mcp_server/server.py
```

Start the FastAPI backend in a second terminal:

```powershell
uvicorn backend.main:app --reload
```

Start the React board in a third terminal:

```powershell
cd frontend
npm install
npm run dev
```

To run all three tickets, reset `data/campus_customs_new.db` first, then run the agent-team entry point for Tickets 101, 102, and 103. Reset the working database again whenever a clean repeatable run is needed. The resulting evidence is recorded in `output/`.

## Problem 8 - Agent dashboard

The React + Vite + TypeScript dashboard is in [Problem 8 - Agent dashboard/frontend](Problem%208%20-%20Agent%20dashboard/frontend/). It connects to the Problem 7 API at `http://localhost:8000`.
