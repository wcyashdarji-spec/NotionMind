from __future__ import annotations

import os
import logfire
from pydantic_ai import Agent
from dotenv import load_dotenv
from pydantic_ai.mcp import MCPToolset
from src.config import logger, get_docs_bearer_token
from src.services.prompt_template import SYSTEM_PROMPT

load_dotenv()
logfire.configure()


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

MODEL_NAME = os.getenv("GEMINI_MODEL")

MCP_URL = os.getenv("MCP_SERVER_URL")

logger.info(f"Initializing Pydantic AI Agent with model={MODEL_NAME} and MCP Server={MCP_URL}")


def _build_toolset(attribute: str) -> MCPToolset:
    """
    Build an :class:`MCPToolset` for the given *attribute* (docs name).

    The Bearer token for the attribute is resolved from environment variables
    at call-time (so token rotations are picked up without a service restart)
    and injected into the ``Authorization`` HTTP header of every MCP request.

    Args:
        attribute: Human-friendly docs / app name sent by the client
            (e.g. ``"Rivyo"`` or ``"Editly_Order_Editing_App_Docs"``).

    Returns:
        A configured :class:`MCPToolset` instance with the appropriate
        ``Authorization`` header set, or no auth header if the attribute
        could not be resolved.
    """
    token = get_docs_bearer_token(attribute)

    if token is None:
        logger.warning(
            f"[Agent] No Bearer token found for attribute '{attribute}'. "
            "MCP calls will proceed without an Authorization header."
        )
        return MCPToolset(MCP_URL)

    if not token.lower().startswith("bearer "):
        token = f"Bearer {token}"

    logger.info(
        f"[Agent] Resolved Bearer token for attribute '{attribute}' "
        f"(env key lookup succeeded, token length={len(token)})."
    )
    return MCPToolset(
        MCP_URL,
        headers={"Authorization": token},
    )


async def ask_agent(prompt: str, attribute: str = "") -> str:
    """
    Execute a user query using the configured Pydantic AI agent.

    A fresh :class:`MCPToolset` is created for every call so that the
    ``Authorization`` header always carries the Bearer token that matches
    *attribute*.  This allows the MCP server to enforce per-collection
    access control without the agent ever holding a cross-collection token.

    Args:
        prompt: The user's input or query to be processed by the AI agent.
        attribute: Human-friendly docs / app name used to resolve the
                   correct Bearer token from environment variables.

    Returns:
        The agent's generated response as a string.

    Raises:
        Exception: Propagates any exception encountered during agent
            execution after logging the error.
    """
    toolset = _build_toolset(attribute)

    local_agent = Agent(
        model=MODEL_NAME,
        system_prompt=SYSTEM_PROMPT,
        toolsets=[toolset],
    )

    logfire.instrument_pydantic_ai(local_agent)

    try:
        logger.info(f"Running agent query: '{prompt}' | attribute='{attribute}'")
        async with toolset:
            result = await local_agent.run(prompt)
            return result.output
    except Exception as exc:
        logger.error(f"Agent execution failed: {exc}")
        raise
