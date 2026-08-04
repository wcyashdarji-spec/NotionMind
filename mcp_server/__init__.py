"""mcp_server package – FastMCP server, registered tools, and shared singletons."""

from __future__ import annotations

_chroma_service = None


def get_chroma_service():
    """
    Return the shared :class:`~src.services.chroma_service.ChromaService`
    instance, creating it on the first call (lazy singleton).

    Returns:
        A connected and ready :class:`ChromaService`.
    """
    global _chroma_service
    if _chroma_service is None:
        from src.config import CHROMA_DB_PATH, logger
        from src.services.chroma_service import ChromaService

        logger.info("[MCP] Initialising ChromaService …")
        _chroma_service = ChromaService(db_path=CHROMA_DB_PATH)
        logger.info("[MCP] ChromaService ready.")
    return _chroma_service


from mcp_server.server import mcp

__all__ = ["mcp", "get_chroma_service"]
