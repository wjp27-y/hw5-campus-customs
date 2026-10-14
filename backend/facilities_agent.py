from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset

from backend.agent_common import build_agent
from backend.models import AgentWorkResult


def create_agent(model_name: str, mcp_server: MCPToolset) -> Agent:
    return build_agent("facilities.md", AgentWorkResult, model_name, mcp_server)
