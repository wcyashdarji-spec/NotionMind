from __future__ import annotations

import os
import logfire
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from src.config import logger
from dotenv import load_dotenv
from src.services.prompt_template import SYSTEM_PROMPT

load_dotenv()
logfire.configure()


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

MODEL_NAME = os.getenv("GEMINI_MODEL")

MCP_URL = os.getenv("MCP_SERVER_URL")

logger.info(f"Initializing Pydantic AI Agent with model={MODEL_NAME} and MCP Server={MCP_URL}")

toolset = MCPToolset(MCP_URL)

agent = Agent(
    model=MODEL_NAME,
    system_prompt=SYSTEM_PROMPT,
    toolsets=[toolset],
)

logfire.instrument_pydantic_ai(agent)

async def ask_agent(prompt: str) -> str:
    """
    Execute a user query using the configured Pydantic AI agent.

    This function sends the provided prompt to the agent, allowing it to
    utilize any tools exposed by the configured MCP server. The MCP toolset
    is managed using an asynchronous context manager to ensure proper
    initialization and cleanup for each request.

    Args:
        prompt: The user's input or query to be processed by the AI agent.

    Returns:
        The agent's generated response as a string.

    Raises:
        Exception: Propagates any exception encountered during agent
            execution after logging the error.
    """
    try:
        logger.info(f"Running agent query: '{prompt}'")
        async with toolset:
            result = await agent.run(prompt)
            return result.output
    except Exception as exc:
        logger.error(f"Agent execution failed: {exc}")
        raise
