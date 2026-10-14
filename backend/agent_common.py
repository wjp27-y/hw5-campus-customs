from __future__ import annotations

from pathlib import Path
import os
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

OutputT = TypeVar("OutputT", bound=BaseModel)
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
SAFETY_POLICY = (
    "Agents must not store customer financial, identifying, or account information. "
    "Agents must not crawl the internet without permission and supervision. "
    "Agents must not use profanity or inappropriate language when responding to customer "
    "queries and complaints. Agents must not perform illegal activities. "
    "Agents must not save customer faces, email addresses, or telephone numbers."
)


def build_agent(
    prompt_file: str,
    output_type: type[OutputT],
    model_name: str,
    mcp_server: MCPToolset,
) -> Agent[None, OutputT]:
    instructions = (
        (PROMPT_DIR / prompt_file).read_text(encoding="utf-8")
        + "\n\nSafety policy:\n"
        + SAFETY_POLICY
    )
    model: str | OpenAIChatModel = model_name
    portkey_key = os.getenv("PORTKEY_API_KEY")
    if portkey_key:
        model_id = model_name.split(":", 1)[1] if ":" in model_name else model_name
        portkey_client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY") or "portkey-gateway",
            base_url="https://api.portkey.ai/v1",
            default_headers={
                "x-portkey-api-key": portkey_key,
                "x-portkey-provider": "openai",
            },
        )
        model = OpenAIChatModel(
            model_id,
            provider=OpenAIProvider(openai_client=portkey_client),
        )
    return Agent(
        model=model,
        instructions=instructions,
        output_type=output_type,
        toolsets=[mcp_server],
    )
