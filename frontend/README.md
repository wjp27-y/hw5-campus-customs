# Campus Customs Agent Dashboard

## Start the dashboard

In a terminal, open this `frontend/` folder and run:

```powershell
npm install
npm run dev
```

Open `http://localhost:5173`. The API is configured at `http://localhost:8000`.

The backend must be running from `Problem 7 - Backend routes/backend` and must have its model provider environment configured. The API allows the local Vite origins `http://localhost:5173` and `http://127.0.0.1:5173`.

Vite 8 requires Node.js 20.19+ or 22.12+; `npm` reports an engine mismatch if the installed Node.js version is too old.
