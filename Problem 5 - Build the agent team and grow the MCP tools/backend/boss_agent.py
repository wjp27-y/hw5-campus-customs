from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset

from backend.agent_common import build_agent
from backend.models import DispatchPlan, TicketResolution


def create_dispatch_agent(model_name: str, mcp_server: MCPToolset) -> Agent:
    return build_agent("boss.md", DispatchPlan, model_name, mcp_server)


def create_resolution_agent(model_name: str, mcp_server: MCPToolset) -> Agent:
    return build_agent("boss.md", TicketResolution, model_name, mcp_server)
