from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MCP_CONFIG = PROJECT_ROOT / ".mcp.json"


def _server_config() -> dict[str, Any]:
    config = json.loads(MCP_CONFIG.read_text(encoding="utf-8"))
    servers = config.get("mcpServers")
    if not isinstance(servers, dict) or "campus-customs" not in servers:
        raise ValueError(f"Campus Customs MCP server is not configured in {MCP_CONFIG}.")
    server = servers["campus-customs"]
    if server.get("type") != "stdio":
        raise ValueError("Campus Customs MCP server must use the stdio transport.")
    return server


def create_mcp_toolset() -> MCPToolset:
    config = _server_config()
    args = [str((PROJECT_ROOT / arg).resolve()) for arg in config["args"]]
    transport = StdioTransport(
        command=sys.executable,
        args=args,
        cwd=str(PROJECT_ROOT),
    )
    return MCPToolset(transport, id="campus-customs")


async def list_open_ticket_ids() -> list[int]:
    config = _server_config()
    args = [str((PROJECT_ROOT / arg).resolve()) for arg in config["args"]]
    params = StdioServerParameters(command=sys.executable, args=args, cwd=str(PROJECT_ROOT))
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("list_tickets", {"status": "open"})
            ticket_rows = result.structuredContent
            if isinstance(ticket_rows, dict):
                ticket_rows = ticket_rows.get("result")
            if result.isError or not isinstance(ticket_rows, list):
                raise RuntimeError(f"Could not list open tickets from MCP server: {result}")
            return [int(ticket["id"]) for ticket in ticket_rows]
