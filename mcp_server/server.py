from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.resolve()))

from fastmcp import FastMCP
from fastapi.responses import PlainTextResponse

from src.services.chroma_service import ChromaService
from src.config import CHROMA_DB_PATH, logger

MCP_HOST: str = "0.0.0.0"
MCP_PORT: int = 8001
MCP_PATH: str = "/mcp"

_chroma_service: ChromaService | None = None


def get_chroma_service() -> ChromaService:
    """
    Return the shared :class:`~src.services.chroma_service.ChromaService`
    instance, creating it on the first call.

    Returns:
        A connected and ready :class:`ChromaService`.
    """
    global _chroma_service
    if _chroma_service is None:
        logger.info("[MCP] Initialising ChromaService …")
        _chroma_service = ChromaService(db_path=CHROMA_DB_PATH)
        logger.info("[MCP] ChromaService ready.")
    return _chroma_service


def create_mcp_server() -> FastMCP:
    """
    Create and configure the Notion Docs MCP server.
    """
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
