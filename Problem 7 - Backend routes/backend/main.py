from __future__ import annotations

import asyncio
import calendar
import json
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_DB = PROJECT_ROOT / "data" / "campus_customs.db"
WORKING_DB = PROJECT_ROOT / "data" / "campus_customs_new.db"
AUDIT_FILE = PROJECT_ROOT / "output" / "audit_trail.json"
PROBLEM_5_ROOT = PROJECT_ROOT / "Problem 5 - Build the agent team and grow the MCP tools"

if str(PROBLEM_5_ROOT) not in sys.path:
    sys.path.insert(0, str(PROBLEM_5_ROOT))

from backend.main import run_team  # noqa: E402

app = FastAPI(
    title="Campus Customs Backend",
    description="Ticket processing, human-approved payments and purchases, and database reset.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)
operation_lock = asyncio.Lock()


class HumanApproval(BaseModel):
    human_approved: Literal[True]
    approved_by: str = Field(min_length=1, max_length=120)


class PaymentApproval(HumanApproval):
    kind: Literal["invoice", "rent"]
    ref_id: int = Field(gt=0)
    ticket_id: int | None = Field(default=None, gt=0)


class PurchaseApproval(HumanApproval):
    ticket_id: int = Field(gt=0)


def _connect() -> sqlite3.Connection:
    if not WORKING_DB.exists():
        raise HTTPException(status_code=503, detail="Working Campus Customs database is missing.")
    connection = sqlite3.connect(WORKING_DB, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _reset_database() -> None:
    if not ORIGINAL_DB.is_file():
        raise FileNotFoundError(f"Original Campus Customs database not found: {ORIGINAL_DB}")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="campus_customs_reset_",
            suffix=".db",
            dir=WORKING_DB.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

        source_uri = f"{ORIGINAL_DB.as_uri()}?mode=ro"
        source = sqlite3.connect(source_uri, uri=True)
        try:
            destination = sqlite3.connect(temporary_path)
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()

        with temporary_path.open("r+b") as database_file:
            os.fsync(database_file.fileno())
        temporary_path.replace(WORKING_DB)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _advance_one_month(due_date: str) -> str:
    current = date.fromisoformat(due_date)
    year = current.year + (1 if current.month == 12 else 0)
    month = 1 if current.month == 12 else current.month + 1
    day = min(current.day, calendar.monthrange(year, month)[1])
    return date(year, month, day).isoformat()


def _cash_balance(connection: sqlite3.Connection) -> dict[str, float | str]:
    row = connection.execute(
        "SELECT name, balance, date FROM cash_accounts WHERE name = 'checking'"
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=503, detail="Checking cash account is not configured.")
    return {"account": row["name"], "balance": float(row["balance"]), "date": row["date"]}


def _ticket_list() -> list[dict[str, object]]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT id, type, subject, sku, size, qty, lease_id, invoice_id, status, created_at
            FROM tickets
            ORDER BY id
            """
        ).fetchall()
    return [
        {
            **dict(row),
            "resolved": row["status"] == "resolved",
            "status": "resolved" if row["status"] == "resolved" else "open",
        }
        for row in rows
    ]


def _audit_events_after(previous_count: int, ticket_id: int) -> list[dict[str, object]]:
    if not AUDIT_FILE.exists():
        return []
    events = json.loads(AUDIT_FILE.read_text(encoding="utf-8"))
    if not isinstance(events, list):
        raise ValueError(f"Audit file must contain a JSON array: {AUDIT_FILE}")
    return [
        event
        for event in events[previous_count:]
        if isinstance(event, dict) and event.get("ticket_id") == ticket_id
    ]


def _count_audit_events() -> int:
    if not AUDIT_FILE.exists():
        return 0
    events = json.loads(AUDIT_FILE.read_text(encoding="utf-8"))
    if not isinstance(events, list):
        raise ValueError(f"Audit file must contain a JSON array: {AUDIT_FILE}")
    return len(events)


def _approve_payment(payload: PaymentApproval) -> dict[str, object]:
    with closing(_connect()) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        if payload.kind == "invoice":
            obligation = connection.execute(
                """
                SELECT id AS ref_id, amount, due_date, status
                FROM invoices
                WHERE id = ?
                """,
                (payload.ref_id,),
            ).fetchone()
            if obligation is None:
                raise HTTPException(status_code=404, detail="Invoice was not found.")
            if obligation["status"] != "open":
                raise HTTPException(status_code=409, detail="Invoice is not open for payment.")
            amount = float(obligation["amount"])
            new_due_date = None
        else:
            obligation = connection.execute(
                "SELECT id AS ref_id, monthly_rent AS amount, next_due AS due_date FROM leases WHERE id = ?",
                (payload.ref_id,),
            ).fetchone()
            if obligation is None:
                raise HTTPException(status_code=404, detail="Lease was not found.")
            amount = float(obligation["amount"])
            new_due_date = _advance_one_month(str(obligation["due_date"]))

        if payload.ticket_id is not None:
            ticket = connection.execute(
                "SELECT invoice_id, lease_id FROM tickets WHERE id = ?",
                (payload.ticket_id,),
            ).fetchone()
            if ticket is None:
                raise HTTPException(status_code=404, detail="Ticket was not found.")
            linked_ref = ticket["invoice_id"] if payload.kind == "invoice" else ticket["lease_id"]
            if linked_ref != payload.ref_id:
                raise HTTPException(
                    status_code=409,
                    detail="The approved obligation is not linked to this ticket.",
                )

        ledger_kind = (
            f"rent:{obligation['due_date']}" if payload.kind == "rent" else payload.kind
        )
        existing = connection.execute(
            "SELECT id FROM payments WHERE kind = ? AND ref_id = ?",
            (ledger_kind, payload.ref_id),
        ).fetchone()
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=f"This {payload.kind} obligation already has a recorded payment.",
            )

        account = _cash_balance(connection)
        if float(account["balance"]) < amount:
            raise HTTPException(
                status_code=409,
                detail="Checking balance is insufficient for this approved obligation.",
            )

        cursor = connection.execute(
            """
            UPDATE cash_accounts
            SET balance = balance - ?
            WHERE name = 'checking' AND balance >= ?
            """,
            (amount, amount),
        )
        if cursor.rowcount != 1:
            raise HTTPException(status_code=409, detail="Checking balance changed; approval was not recorded.")

        paid_at = datetime.now(timezone.utc).isoformat()
        payment_cursor = connection.execute(
            """
            INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by)
            VALUES (?, ?, ?, 'checking', ?, ?)
            """,
            (ledger_kind, payload.ref_id, amount, paid_at, payload.approved_by.strip()),
        )
        if payload.kind == "invoice":
            connection.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (payload.ref_id,))
        else:
            connection.execute(
                "UPDATE leases SET next_due = ? WHERE id = ?",
                (new_due_date, payload.ref_id),
            )
        if payload.ticket_id is not None:
            connection.execute(
                "UPDATE tickets SET status = 'resolved' WHERE id = ?",
                (payload.ticket_id,),
            )

        return {
            "payment_id": payment_cursor.lastrowid,
            "kind": payload.kind,
            "ref_id": payload.ref_id,
            "amount_paid": amount,
            "approved_by": payload.approved_by.strip(),
            "cash_account": _cash_balance(connection),
            "ticket_status": "resolved" if payload.ticket_id is not None else None,
        }


def _approve_purchase(payload: PurchaseApproval) -> dict[str, object]:
    with closing(_connect()) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        ticket = connection.execute(
            """
            SELECT id, sku, size, qty, status
            FROM tickets
            WHERE id = ?
            """,
            (payload.ticket_id,),
        ).fetchone()
        if ticket is None:
            raise HTTPException(status_code=404, detail="Purchase ticket was not found.")
        if not ticket["sku"] or not ticket["size"] or not ticket["qty"] or ticket["qty"] <= 0:
            raise HTTPException(status_code=409, detail="Ticket has no valid item and quantity to purchase.")

        existing = connection.execute(
            "SELECT id FROM payments WHERE kind = 'purchase_order' AND ref_id = ?",
            (payload.ticket_id,),
        ).fetchone()
        if existing is not None:
            raise HTTPException(status_code=409, detail="A purchase for this ticket has already been recorded.")

        pricing = connection.execute(
            "SELECT unit_cost FROM pricing WHERE sku = ?",
            (ticket["sku"],),
        ).fetchone()
        if pricing is None:
            raise HTTPException(status_code=409, detail="No catalog unit cost is available for this ticket.")
        amount = round(float(pricing["unit_cost"]) * int(ticket["qty"]), 2)
        if amount <= 0:
            raise HTTPException(status_code=409, detail="Calculated purchase cost must be positive.")

        account = _cash_balance(connection)
        if float(account["balance"]) < amount:
            raise HTTPException(
                status_code=409,
                detail="Checking balance is insufficient for this approved purchase.",
            )
        cursor = connection.execute(
            """
            UPDATE cash_accounts
            SET balance = balance - ?
            WHERE name = 'checking' AND balance >= ?
            """,
            (amount, amount),
        )
        if cursor.rowcount != 1:
            raise HTTPException(status_code=409, detail="Checking balance changed; approval was not recorded.")

        paid_at = datetime.now(timezone.utc).isoformat()
        payment_cursor = connection.execute(
            """
            INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by)
            VALUES ('purchase_order', ?, ?, 'checking', ?, ?)
            """,
            (payload.ticket_id, amount, paid_at, payload.approved_by.strip()),
        )
        connection.execute(
            "UPDATE tickets SET status = 'resolved' WHERE id = ?",
            (payload.ticket_id,),
        )
        return {
            "payment_id": payment_cursor.lastrowid,
            "kind": "purchase_order",
            "ticket_id": payload.ticket_id,
            "sku": ticket["sku"],
            "size": ticket["size"],
            "qty": ticket["qty"],
            "amount_paid": amount,
            "approved_by": payload.approved_by.strip(),
            "cash_account": _cash_balance(connection),
            "ticket_status": "resolved",
        }


@app.get("/tickets")
async def get_tickets() -> dict[str, object]:
    return {"tickets": await asyncio.to_thread(_ticket_list)}


@app.post("/tickets/{ticket_id}/run")
async def run_ticket(ticket_id: int) -> dict[str, object]:
    return await _execute_ticket(ticket_id)


async def _execute_ticket(ticket_id: int, progress=None) -> dict[str, object]:
    async with operation_lock:
        if ticket_id not in {int(ticket["id"]) for ticket in await asyncio.to_thread(_ticket_list)}:
            raise HTTPException(status_code=404, detail="Ticket was not found.")
        await asyncio.to_thread(_reset_database)
        previous_count = await asyncio.to_thread(_count_audit_events)
        try:
            reports = await run_team(ticket_id, progress=progress)
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        if not reports:
            raise HTTPException(status_code=500, detail="Agent team returned no ticket report.")

        report = reports[0]
        resolved = report.resolution.status == "resolved"
        await asyncio.to_thread(
            _set_ticket_status,
            ticket_id,
            "resolved" if resolved else "open",
        )
        events = await asyncio.to_thread(_audit_events_after, previous_count, ticket_id)
        return {
            "ticket_id": ticket_id,
            "status": "resolved" if resolved else "open",
            "resolved": resolved,
            "boss": {
                "dispatch_plan": report.plan.model_dump(mode="json"),
                "final_judgment": report.resolution.model_dump(mode="json"),
                "tools_used": sorted(
                    {
                        tool
                        for event in events
                        if event.get("agent") == "boss"
                        for tool in event.get("tool_names", [])
                    }
                ),
            },
            "agents": [
                {
                    **agent_result.model_dump(mode="json"),
                    "tools_used": sorted(
                        {
                            tool
                            for event in events
                            if event.get("agent") == agent_result.agent
                            for tool in event.get("tool_names", [])
                        }
                    ),
                }
                for agent_result in report.agent_results
            ],
            "customer_reply": (
                report.customer_reply.model_dump(mode="json")
                if report.customer_reply is not None
                else None
            ),
        }


@app.post("/tickets/{ticket_id}/run/stream")
async def stream_ticket_run(ticket_id: int) -> StreamingResponse:
    queue: asyncio.Queue[tuple[str, object] | None] = asyncio.Queue()

    async def publish(event: dict[str, object]) -> None:
        await queue.put(("progress", event))

    async def execute_and_publish() -> None:
        try:
            result = await _execute_ticket(ticket_id, progress=publish)
            await queue.put(("complete", result))
        except HTTPException as error:
            await queue.put(("error", {"status_code": error.status_code, "detail": error.detail}))
        except Exception as error:
            await queue.put(("error", {"status_code": 500, "detail": str(error)}))
        finally:
            await queue.put(None)

    async def event_stream():
        task = asyncio.create_task(execute_and_publish())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                event_name, payload = item
                yield f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _set_ticket_status(ticket_id: int, status: str) -> None:
    with closing(_connect()) as connection, connection:
        cursor = connection.execute(
            "UPDATE tickets SET status = ? WHERE id = ?",
            (status, ticket_id),
        )
        if cursor.rowcount != 1:
            raise HTTPException(status_code=404, detail="Ticket was not found.")


@app.get("/cash")
async def get_cash_balance() -> dict[str, object]:
    with closing(_connect()) as connection:
        return {"cash_account": _cash_balance(connection)}


@app.post("/approvals/payment")
async def approve_payment(payload: PaymentApproval) -> dict[str, object]:
    if not payload.approved_by.strip():
        raise HTTPException(status_code=422, detail="approved_by must not be blank.")
    async with operation_lock:
        return await asyncio.to_thread(_approve_payment, payload)


@app.post("/approvals/purchase")
async def approve_purchase(payload: PurchaseApproval) -> dict[str, object]:
    if not payload.approved_by.strip():
        raise HTTPException(status_code=422, detail="approved_by must not be blank.")
    async with operation_lock:
        return await asyncio.to_thread(_approve_purchase, payload)


@app.post("/database/reset")
async def reset_database() -> dict[str, object]:
    async with operation_lock:
        await asyncio.to_thread(_reset_database)
        with closing(_connect()) as connection:
            tickets_reset = int(
                connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
            )
            cash_account = _cash_balance(connection)
        return {
            "database": "data/campus_customs_new.db",
            "restored_from": "data/campus_customs.db",
            "tickets_reset": tickets_reset,
            "cash_account": cash_account,
        }
