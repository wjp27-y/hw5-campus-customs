from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset

from backend.agent_common import build_agent
from backend.models import CustomerReply


def create_agent(model_name: str, mcp_server: MCPToolset) -> Agent:
    return build_agent("customer_service.md", CustomerReply, model_name, mcp_server)
