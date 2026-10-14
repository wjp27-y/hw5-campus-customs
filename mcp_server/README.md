# Campus Customs MCP Server

This MCP server is a "tool belt" for the agent: it exposes narrow, business-relevant actions and data access points that let an AI accomplish real work against the Campus Customs operational database without exposing the whole database at once.

In MCP terms, the server acts like a controlled interface between the agent and the system. The agent can ask for tools to inspect stock, evaluate cash and obligations, and quote pricing, and each tool returns structured data the agent can use to make decisions.

## Database

The server connects to the working database copy used for the assignment:

- `../../data/campus_customs_new.db`

This file is the editable copy that future tasks can update.

## Tools exposed by the server

The server exposes tools to support customer and internal-agent workflows:

1. `list_tickets(status)`
   - Lists ticket work without returning requester identities.

2. `get_ticket(ticket_id)`
   - Returns the details required to work a ticket, omitting the requester field.

3. `check_stock(sku, size)`
   - Reads inventory, invoice data, and vendor information to determine whether a requested item can be fulfilled and how long a reprint will take.

4. `check_cash_and_obligations(as_of)`
   - Reads the current desk date, cash balance, lease due date, and open invoice obligations to tell the agent what can safely be paid.

5. `quote_price(sku, qty, discount_pct, size)`
   - Reads pricing and inventory to calculate the effective order price after a discount. The optional `size` reports whether that size has enough units, as well as total stock across sizes.

6. `draft_purchase_order(sku, size, qty)`
   - Prepares a non-binding restock cost/vendor/lead-time estimate. It does not create an order or payment.

All business-data access remains through this MCP server. The MCP tools do not update tickets, place orders, or issue payments.

## How to run it

From the project root:

```bash
python "Problem 3 - Build the MCP server\mcp_server\server.py"
```

The server uses FastMCP and communicates over stdio so it can be connected by an MCP client.
