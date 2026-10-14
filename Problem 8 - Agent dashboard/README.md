# Problem 8 - Agent dashboard

The runnable frontend lives in `frontend/`. It is a React + Vite + TypeScript app connected to the Problem 7 FastAPI backend.

## Run

Start the backend from `Problem 7 - Backend routes/backend` at `http://localhost:8000`, with the Problem 5 model provider configured. Then open a second terminal in this problem's `frontend/` directory:

```powershell
npm install
npm run dev
```

Open `http://localhost:5173`. The board lists all tickets, lets the user select one, and streams the agent team's progress while it runs. If the team's report recommends a payment or purchase, the dashboard presents a human confirmation dialog before posting to the approval route. The checking balance and board refresh after an approval.

The UI uses the API routes documented in Problem 7. Its streaming run route is `POST /tickets/{ticket_id}/run/stream`; progress events are emitted between team and specialist steps, with the final report sent when the run completes.
