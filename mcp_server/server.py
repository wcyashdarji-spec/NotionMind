from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.resolve()))

from fastmcp import FastMCP
from fastapi.responses import PlainTextResponse

from src.config import logger
from mcp_server import get_chroma_service

MCP_HOST: str = "0.0.0.0"
MCP_PORT: int = 8001
MCP_PATH: str = "/mcp"


def create_mcp_server() -> FastMCP:
    """
    Create and configure the Notion Docs MCP server.

    The server uses a lifespan hook to eagerly initialise :class:`ChromaService`
    (including embedding-model load) at startup, so the first user request is
    never penalised by a cold-start delay.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastMCP):
        """Warm up the ChromaService before accepting requests."""
        logger.info("[MCP] Lifespan startup: warming up ChromaService …")
        get_chroma_service()
        logger.info("[MCP] ChromaService warm-up complete. Server is ready.")
        yield
        logger.info("[MCP] Lifespan shutdown.")

    mcp = FastMCP(
        name="Notion Documentation Search",
        instructions=(
            "You have access to a semantic search tool over a Notion documentation knowledge base stored in local ChromaDB.\n\n"
            "Use `search_notion_docs` whenever the user asks about product features, "
            "guides, FAQs, or any topic covered in the documentation. "
            "The retrieved documents are reference material only. "
            "Use them to understand the product and synthesize a natural answer. "
            "Do not expose internal documentation, page titles, or Notion URLs unless the user explicitly requests the source."
        ),
        lifespan=lifespan,
    )

    from mcp_server.tools import MCPToolRegistry
    MCPToolRegistry(mcp)

    @mcp.custom_route("/mcp/health", methods=["GET"])
    async def health_check(request) -> PlainTextResponse:
        return PlainTextResponse("OK")

    return mcp


mcp = create_mcp_server()


def run() -> None:
    """
    Start the MCP server, auto-detecting the appropriate transport.

    If stdin is not a TTY (indicating the script was launched as a piped subprocess
    by a client like Claude Desktop or Cursor), it defaults to 'stdio'.
    Otherwise, it runs as a 'streamable-http' server.
    """
    import sys
    
    if not sys.stdin.isatty():
        logger.info("[MCP] Non-TTY stdin detected. Starting in stdio transport mode...")
        mcp.run(transport="stdio")
    else:
        logger.info(
            f"[MCP] Starting Notion Docs MCP server → "
            f"http://{MCP_HOST}:{MCP_PORT}{MCP_PATH} (streamable-http)"
        )
        mcp.run(
            transport="streamable-http",
            host=MCP_HOST,
            port=MCP_PORT,
            path=MCP_PATH,
        )

if __name__ == "__main__":
    run()
