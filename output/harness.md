The 3 MCP tools I will need are:      check_stock(sku,size) which unlocks ticket 101 since it reads invoices, vendors, and inventory. This is the right tool for Ticket 101 since it matches the white tshirt and is able to show stock, an invoice attached to it, and the delivery estimate with Bulldog Print Co as vendor 1.

check_cash_and_obligations(as of) unlocks ticket 102, since it reads desk, leases, cash_accounts, and invoices. This fits since Ticket 102 is an email with a date, cash account, lease, and invoice.

quote_price(sku,qty,discount_pct) unlocks ticket 103 because it reads pricing and invetory, as Ticket 103 has both a unit price of the navy hoodie and a list price, with inventory of the hoodies needed.

## Problem 5 — Agent team and MCP tools

| Agent | MCP tools used |
|---|---|
| Boss | `list_tickets(status)`, `get_ticket(ticket_id)` to read and assign each ticket; uses specialist findings to make the final resolution judgment. |
| Inventory | `get_ticket(ticket_id)`, `check_stock(sku, size)`, `draft_purchase_order(sku, size, qty)` to check size-specific stock, vendor fit, and non-binding restock estimates. |
| Accounting | `get_ticket(ticket_id)`, `check_cash_and_obligations(as_of)`, `quote_price(sku, qty, discount_pct, size?)`, `draft_purchase_order(sku, size, qty)` to review cash, invoices, margins, and size-specific draft order costs. |
| Facilities | `get_ticket(ticket_id)`, `check_cash_and_obligations(as_of)` to review lease, rent, and cash obligations. |
| Customer Service | `get_ticket(ticket_id)` and the findings returned by other agents; drafts customer replies only after the Boss's resolution. |

Purchase-order drafts are non-binding estimates. The MCP server does not place orders, issue payments, or modify ticket records.

### Safety

Agents must not store customer financial, identifying, or account information. Agents must not crawl the internet without permission and supervision. Agents must not use profanity or inappropriate language when responding to customer queries and complaints. Agents must not perform illegal activities. Agents must not save customer faces, email addresses, or telephone numbers.

## Problem 7 — Backend routes

- `GET http://127.0.0.1:8000/tickets` returns Tickets 101, 102, and 103 with each ticket's resolved/open status.
- `POST http://127.0.0.1:8000/tickets/{ticket_id}/run` restores the working database from its original values, runs the agent team for that ticket, and returns what the agents said and which MCP tools they used.
- `GET http://127.0.0.1:8000/cash` returns the up-to-date checking balance from `cash_accounts`.
- `POST http://127.0.0.1:8000/approvals/payment` records a human-approved invoice or rent payment and returns the updated checking balance.
- `POST http://127.0.0.1:8000/approvals/purchase` records a human-approved purchase for a ticket and returns the updated checking balance.
- `POST http://127.0.0.1:8000/database/reset` restores `campus_customs_new.db` from the original `campus_customs.db` and reports the reset ticket count and checking balance.

Start the backend from the Problem 7 `backend` folder with `uvicorn main:app --reload --port 8000`.

## Problem 8 - Agent dashboard

`Problem 8 - Agent dashboard/frontend/` contains the React + Vite + TypeScript UI. Start it from that folder with `npm install` followed by `npm run dev`; Vite serves the dashboard at `http://localhost:5173` and the frontend calls the Problem 7 API at `http://localhost:8000`.

The board loads all three tickets from `GET /tickets` and the current checking balance from `GET /cash`. Selecting a ticket enables a team run. The frontend calls `POST /tickets/{ticket_id}/run/stream` and renders dispatch, specialist findings, recommendations, tool names, and Kakashi's final decision as server-sent events arrive. It then refreshes the ticket board and balance.

`POST http://localhost:8000/tickets/{ticket_id}/run/stream` runs a ticket and streams the live team activity and final report; the frontend uses this endpoint so agent assignments and findings appear as each team step completes.

Problem 7's FastAPI application allows the Vite origins `http://localhost:5173` and `http://127.0.0.1:5173`. The existing JSON run route remains available. Payment and purchase suggestions open an explicit approval dialog; confirming calls the existing `/approvals/payment` or `/approvals/purchase` route, refreshes the checking balance, and resolves the ticket after successful approval. The approval dialog is a local coursework confirmation and does not authenticate the approver or contact a vendor.

The dashboard's Yale blue, silver, and white visual choices and the Kakashi/Team 7 role icons are recorded in [output/design.md](design.md).

## Problem 9 — Resolution, approvals, and safety run

The reset restored `data/campus_customs_new.db` from `data/campus_customs.db` with a starting checking balance of $3,400.00. The three Portkey agent runs were recorded in `output/audit_trail.json`; the later human approval events use the same audit trail with the `human_approval` step.

The authorized approval run used the existing backend approval paths: a $8.00 purchase approval for Ticket 101, a $2,400.00 rent payment for Ticket 102, and a $440.00 purchase approval for Ticket 103. The ending checking balance is $552.00, matching `cash_accounts` in the working database. No vendor was contacted and no customer-identifying information was added to the persistent outputs.

The resolved dashboard snapshot is [output/resolved_board.html](resolved_board.html), and its structured source is [output/resolved_tickets.json](resolved_tickets.json). The original planning page records the requested Actual sections and Cash tab ledger in [output/desk_tickets.html](desk_tickets.html).

### Data tables used by the harness

| Table | Purpose |
|---|---|
| `tickets` | Ticket subjects, SKU/size/quantity, linked lease or invoice, and resolved/open status. |
| `inventory` | Size-specific stock, location, and item names used by `check_stock` and `quote_price`. |
| `pricing` | Unit cost and list price used by `quote_price` and approval purchase calculations. |
| `vendors` | Matching vendor and estimated lead-time evidence for restock drafts. |
| `invoices` | Open vendor obligations reviewed by Accounting and linked to Ticket 101. |
| `leases` | Rent amount and next due date reviewed by Facilities and linked to Ticket 102. |
| `cash_accounts` | Checking balance and as-of date; source of the $3,400.00 reset balance and $552.00 ending balance. |
| `payments` | Approved invoice, rent, and purchase-order ledger entries that explain cash changes. |
| `desk` | Business as-of date used by obligation checks. |

Yes: before this section, the harness already documented the agents, their MCP tools, the API routes, the dashboard workflow, and safety policy. This Problem 9 section adds the database tables, approval cash ledger, resolved artifacts, and the safety-run record.
