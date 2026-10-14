# Problem 7 — Backend routes

This FastAPI app serves the Campus Customs agent team and human-approved financial actions.

## Start the backend

Open a terminal in this section's `backend` folder, install `requirements.txt`, configure the model provider environment variables used by Problem 5, then start the development server:

```powershell
python -m pip install -r requirements.txt
$env:PYDANTIC_AI_MODEL = "openai:gpt-4o-mini"
uvicorn main:app --reload --port 8000
```

The browser API docs are available at `http://127.0.0.1:8000/docs`.

Every `POST /tickets/{ticket_id}/run` resets `data/campus_customs_new.db` from the original `data/campus_customs.db` before running the team. The reset endpoint can also be called explicitly.

Payment and purchase approval endpoints require `human_approved: true` and a non-empty `approved_by` value. In this coursework app, those fields record explicit human approval; they do not authenticate the approver. Do not expose the approval routes publicly without adding authentication and authorization.

Purchase approvals are bound to the SKU, size, and quantity of the specified ticket and use its catalog unit cost. They debit the checking account and append a payment-ledger row; the API does not contact a vendor.

## Routes

- `GET /tickets` lists all three tickets and indicates whether each is resolved or open.
- `POST /tickets/{ticket_id}/run` resets the working database to its original values, runs the agent team for that ticket, records its status, and returns agent statements and MCP tools used.
- `GET /cash` returns the current checking-account balance.
- `POST /approvals/payment` records a human-approved invoice or rent payment and returns the updated checking balance.
- `POST /approvals/purchase` records a human-approved purchase for a ticket and returns the updated checking balance.
- `POST /database/reset` restores the working database from the original database and returns the reset ticket count and checking balance.
- `POST /tickets/{ticket_id}/run/stream` runs the same workflow and streams progress events and the final report for the dashboard.

The API allows browser requests from `http://localhost:5173` and `http://127.0.0.1:5173` for the local Vite dashboard.

Approval request bodies must contain `human_approved: true` and `approved_by`. A payment request also contains `kind` (`invoice` or `rent`) and `ref_id`; a purchase request contains `ticket_id`.

## Files

- `backend/main.py`: FastAPI application and route handlers.
- `backend/requirements.txt`: API and agent runtime dependencies.
