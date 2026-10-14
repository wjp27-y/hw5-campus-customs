from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "campus_customs_new.db"

mcp = FastMCP("Campus Customs")


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


@mcp.tool()
def list_tickets(status: str | None = None) -> list[dict[str, Any]]:
    """List work tickets, optionally filtered by status, without exposing requester identities."""
    if status is not None and status not in {"open", "in_progress", "resolved", "blocked"}:
        raise ValueError("status must be open, in_progress, resolved, or blocked.")

    query = """
        SELECT id, type, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at
        FROM tickets
    """
    parameters: tuple[str, ...] = ()
    if status is not None:
        query += " WHERE status = ?"
        parameters = (status,)
    query += " ORDER BY id"

    with _connect() as conn:
        return [dict(row) for row in conn.execute(query, parameters).fetchall()]


@mcp.tool()
def get_ticket(ticket_id: int) -> dict[str, Any] | None:
    """Get ticket details for agent work, omitting requester identifying information."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, type, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at
            FROM tickets
            WHERE id = ?
            """,
            (ticket_id,),
        ).fetchone()
        return dict(row) if row is not None else None


@mcp.tool()
def check_stock(sku: str, size: str) -> dict[str, Any]:
    """Inspect stock and vendor data for a SKU/size, including related invoices and delivery lead time."""
    with _connect() as conn:
        inventory_row = conn.execute(
            """
            SELECT sku, size, qty, location, name
            FROM inventory
            WHERE sku = ? AND size = ?
            """,
            (sku, size),
        ).fetchone()

        if inventory_row is None:
            return {
                "sku": sku,
                "size": size,
                "inventory": None,
                "invoice": None,
                "vendor": None,
                "ready_for_fulfillment": False,
                "notes": "No matching inventory row found for the requested SKU and size.",
            }

        invoice_row = conn.execute(
            """
            SELECT i.id, i.vendor_id, i.amount, i.due_date, i.status, i.description, v.name AS vendor_name, v.lead_days
            FROM invoices i
            LEFT JOIN vendors v ON v.id = i.vendor_id
            WHERE i.description LIKE ? AND i.description LIKE ?
            ORDER BY i.id DESC
            LIMIT 1
            """,
            (f"%{sku}%", f"%{size}%"),
        ).fetchone()

        vendor_row = None
        if invoice_row is not None and invoice_row["vendor_id"] is not None:
            vendor_row = conn.execute(
                "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?",
                (invoice_row["vendor_id"],),
            ).fetchone()

        return {
            "sku": sku,
            "size": size,
            "inventory": dict(inventory_row),
            "invoice": dict(invoice_row) if invoice_row is not None else None,
            "vendor": dict(vendor_row) if vendor_row is not None else None,
            "estimated_reprint_lead_days": (
                int(vendor_row["lead_days"]) if vendor_row is not None else None
            ),
            "ready_for_fulfillment": (inventory_row["qty"] > 0),
            "notes": (
                "Stock is available for immediate fulfillment."
                if inventory_row["qty"] > 0
                else "No stock is available in this size; a reprint may be needed."
            ),
        }


@mcp.tool()
def check_cash_and_obligations(as_of: str) -> dict[str, Any]:
    """Review cash on hand, upcoming lease obligations, and open invoices as of a given date."""
    as_of_date = date.fromisoformat(as_of)
    with _connect() as conn:
        desk_row = conn.execute(
            "SELECT date_today, notes FROM desk LIMIT 1"
        ).fetchone()
        cash_row = conn.execute(
            "SELECT name, balance, date FROM cash_accounts ORDER BY name LIMIT 1"
        ).fetchone()
        lease_row = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases ORDER BY id LIMIT 1"
        ).fetchone()
        invoices = conn.execute(
            "SELECT id, vendor_id, amount, due_date, status, description FROM invoices WHERE status = 'open' ORDER BY due_date"
        ).fetchall()

        overdue = []
        upcoming = []
        for row in invoices:
            invoice = dict(row)
            if row["due_date"] < as_of:
                overdue.append(invoice)
            else:
                upcoming.append(invoice)

        total_open = sum(float(row["amount"]) for row in invoices)
        if cash_row is None:
            raise RuntimeError("No cash account is configured.")
        if lease_row is None:
            raise RuntimeError("No lease is configured.")

        balance = float(cash_row["balance"])
        days_until_rent_due = (
            date.fromisoformat(lease_row["next_due"]) - as_of_date
        ).days
        total_obligations = total_open + float(lease_row["monthly_rent"])

        return {
            "as_of": as_of,
            "desk": dict(desk_row) if desk_row is not None else None,
            "cash_account": dict(cash_row) if cash_row is not None else None,
            "balance": balance,
            "lease": dict(lease_row) if lease_row is not None else None,
            "days_until_rent_due": days_until_rent_due,
            "rent_due_in_two_days": days_until_rent_due == 2,
            "open_invoice_total": total_open,
            "total_obligations_including_next_rent": total_obligations,
            "balance_after_obligations": round(balance - total_obligations, 2),
            "overdue_invoices": overdue,
            "upcoming_invoices": upcoming,
            "can_cover_obligations": balance >= total_obligations,
            "notes": (
                "Cash balance covers the next rent payment and all open invoices."
                if balance >= total_obligations
                else "Cash balance is below total open obligations and should be reviewed before paying vendors."
            ),
        }


@mcp.tool()
def quote_price(
    sku: str,
    qty: int,
    discount_pct: float = 0.0,
    size: str | None = None,
) -> dict[str, Any]:
    """Calculate the order price for a SKU and quantity after a discount, while checking available inventory."""
    if qty < 0:
        raise ValueError("qty must be non-negative.")
    if discount_pct < 0 or discount_pct > 100:
        raise ValueError("discount_pct must be between 0 and 100.")

    with _connect() as conn:
        pricing_row = conn.execute(
            "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
            (sku,),
        ).fetchone()

        inventory_rows = conn.execute(
            "SELECT sku, size, qty, location, name FROM inventory WHERE sku = ?",
            (sku,),
        ).fetchall()

        if pricing_row is None:
            return {
                "sku": sku,
                "qty": qty,
                "discount_pct": discount_pct,
                "pricing": None,
                "inventory": [],
                "quote": None,
                "notes": "No pricing row found for the requested SKU.",
            }

        list_price = float(pricing_row["list_price"])
        discounted_price = list_price * (1 - (float(discount_pct) / 100.0))
        total_price = discounted_price * qty
        total_available = sum(int(row["qty"]) for row in inventory_rows)
        available_for_size = (
            sum(int(row["qty"]) for row in inventory_rows if row["size"] == size)
            if size is not None
            else None
        )

        return {
            "sku": sku,
            "qty": qty,
            "requested_size": size,
            "discount_pct": discount_pct,
            "pricing": {
                "unit_cost": float(pricing_row["unit_cost"]),
                "list_price": list_price,
                "discounted_unit_price": discounted_price,
            },
            "inventory": [dict(row) for row in inventory_rows],
            "total_available_across_sizes": total_available,
            "available_for_requested_size": available_for_size,
            "sufficient_for_requested_size": (
                available_for_size >= qty if available_for_size is not None else None
            ),
            "quote": {
                "subtotal": round(total_price, 2),
                "estimated_margin": round((discounted_price - float(pricing_row["unit_cost"])) * qty, 2),
            },
            "notes": (
                "Inventory is sufficient in the requested size."
                if available_for_size is not None and available_for_size >= qty
                else (
                    "Inventory is below the requested quantity in the requested size."
                    if available_for_size is not None
                    else "Inventory is listed by size; confirm the requested size has enough stock before promising fulfillment."
                )
            ),
        }


@mcp.tool()
def draft_purchase_order(sku: str, size: str, qty: int) -> dict[str, Any]:
    """Draft a non-binding restock purchase order using current stock, unit cost, and matching vendor lead time."""
    if qty <= 0:
        raise ValueError("qty must be a positive integer.")

    with _connect() as conn:
        stock = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
        pricing = conn.execute(
            "SELECT unit_cost FROM pricing WHERE sku = ?",
            (sku,),
        ).fetchone()
        if pricing is None:
            return {
                "sku": sku,
                "size": size,
                "qty": qty,
                "purchase_order": None,
                "notes": "Cannot draft an order because no unit cost exists for this SKU.",
            }

        if sku.startswith(("CC-TEE-", "CC-HOOD-", "CC-HAT-")):
            specialty = "%apparel%"
        elif sku.startswith("CC-MUG-"):
            specialty = "%mugs%"
        else:
            return {
                "sku": sku,
                "size": size,
                "qty": qty,
                "purchase_order": None,
                "notes": "No matching restock vendor category is known for this SKU.",
            }

        vendor = conn.execute(
            """
            SELECT id, name, specialty, lead_days
            FROM vendors
            WHERE specialty LIKE ?
            ORDER BY lead_days, id
            LIMIT 1
            """,
            (specialty,),
        ).fetchone()
        if vendor is None:
            return {
                "sku": sku,
                "size": size,
                "qty": qty,
                "purchase_order": None,
                "notes": "No matching vendor is configured; no order was drafted.",
            }

        unit_cost = float(pricing["unit_cost"])
        return {
            "sku": sku,
            "size": size,
            "current_stock": dict(stock) if stock is not None else None,
            "qty_to_order": qty,
            "vendor": dict(vendor),
            "estimated_unit_cost": unit_cost,
            "estimated_total_cost": round(unit_cost * qty, 2),
            "estimated_lead_days": int(vendor["lead_days"]),
            "purchase_order": {
                "status": "draft",
                "committed": False,
                "note": "This is a quote only; it does not create a purchase order or payment.",
            },
            "notes": "Review and approve this draft before contacting the vendor.",
        }


if __name__ == "__main__":
    mcp.run(transport="stdio")
