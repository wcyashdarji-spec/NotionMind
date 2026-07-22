from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.resolve()))

from fastmcp import FastMCP
from fastapi.responses import PlainTextResponse

from src.services.milvus_service import MilvusService
from src.config import MILVUS_ENDPOINT, MILVUS_TOKEN, logger

MCP_HOST: str = "0.0.0.0"
MCP_PORT: int = 8001
MCP_PATH: str = "/mcp"

_milvus_service: MilvusService | None = None


def get_milvus_service() -> MilvusService:
    """
    Return the shared :class:`~src.services.milvus_service.MilvusService`
    instance, creating it on the first call.

    Returns:
        A connected and ready :class:`MilvusService`.

    Raises:
        RuntimeError: When ``MILVUS_ENDPOINT`` or ``MILVUS_TOKEN`` are not set.
    """
    global _milvus_service
    if _milvus_service is None:
        if not MILVUS_ENDPOINT or not MILVUS_TOKEN:
            raise RuntimeError(
                "MILVUS_ENDPOINT and MILVUS_TOKEN must be set in the environment "
                "before the MCP server can serve search requests."
            )
        logger.info("[MCP] Initialising MilvusService …")
        _milvus_service = MilvusService(uri=MILVUS_ENDPOINT, token=MILVUS_TOKEN)
        logger.info("[MCP] MilvusService ready.")
    return _milvus_service


def create_mcp_server() -> FastMCP:
    """
    Create and configure the Notion Docs MCP server.
    """
    mcp = FastMCP(
        name="Notion Documentation Search",
        instructions=(
            "You have access to a semantic search tool over a Notion documentation knowledge base stored in Zilliz Milvus.\n\n"
            "Workflow Requirement:\n"
            "1. Whenever you need to search documentation, execute `search_notion_docs`.\n"
            "2. Immediately after executing `search_notion_docs`, execute the tool `notion_doc_qa_prompt` to retrieve the mandatory grounding, style, and quality control guidelines.\n"
            "3. You MUST strictly follow the rules returned by `notion_doc_qa_prompt` as high-priority system-level instructions when formulating your final answer."
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
