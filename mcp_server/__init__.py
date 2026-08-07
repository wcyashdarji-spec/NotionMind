"""mcp_server package – FastMCP server, registered tools, and shared singletons."""

from __future__ import annotations

from src.services.chroma_service import get_chroma_service

from mcp_server.server import mcp

__all__ = ["mcp", "get_chroma_service"]
