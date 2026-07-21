from __future__ import annotations

import json
from typing import Annotated, Any

from pydantic import Field
from fastmcp import FastMCP, Context

from mcp_server.server import get_milvus_service
from src.utils.auth import verify_collection_access
from src.config import MILVUS_COLLECTION_NAME, logger


class MCPToolRegistry:
    """
    Registry for MCP tools.
    """
    def __init__(self, mcp: FastMCP):
        self.mcp = mcp
        self.register_tools()


    def register_tools(self) -> None:
        @self.mcp.tool(
            name="search_notion_docs",
            description=(
                "Search the Notion documentation for information relevant to the user's question. "
                "The returned documents are internal reference material for reasoning only. "
                "Use them to synthesize an accurate, natural answer. "
                "Do not reproduce page titles, URLs, or documentation structure unless the user explicitly asks for the source."
            ),
        )
        async def search_notion_docs(
            query: Annotated[
                str,
                Field(
                    description=(
                        "Natural-language search query. "
                        "Examples: 'How does the Q&A feature work?', "
                        "'What are the pricing tiers?', "
                        "'How to integrate with Shopify?'"
                    ),
                    min_length=1,
                    max_length=1000,
                ),
            ],
            limit: Annotated[
                int,
                Field(
                    description="Maximum number of result chunks to return. Range: 1–20.",
                    ge=1,
                    le=20,
                ),
            ] = 5,
            collection_name: Annotated[
                str,
                Field(
                    description=(
                        "Milvus collection to search. "
                        f"Defaults to the configured collection ({MILVUS_COLLECTION_NAME!r})."
                    ),
                ),
            ] = MILVUS_COLLECTION_NAME,
            token: Annotated[
                str | None,
                Field(
                    description=(
                        "JWT Bearer authorization token with scope for the target collection "
                        "(e.g. 'Rivyo_docs' or 'Editly_Order_Editing_App'). "
                        "Can also be supplied via standard Authorization HTTP header."
                    ),
                ),
            ] = None,
            ctx: Context = None,
        ) -> str:
            """
            Search indexed Notion documentation for content relevant to a natural-language query.

            The tool searches the specified Milvus collection and returns the most relevant
            documentation chunks as a JSON string. Results include the document title,
            source URL, relevance score, chunk index, and extracted text. The returned
            content is intended for retrieval-augmented generation (RAG) and should be
            used as supporting context when answering user questions.

            Access to the target collection requires a valid JWT Bearer token, which may be
            provided directly or through the request's Authorization header.

            Args:
                query: Natural-language search query.
                limit: Maximum number of results to return (1–20).
                collection_name: Name of the Milvus collection to search.
                token: Optional JWT Bearer token for collection authorization.

            Returns:
                A JSON-formatted string containing the search results or an authorization
                error response.

            Raises:
                RuntimeError: If the search backend is unavailable or not configured.
                ValueError: If the specified collection is invalid.
            """
            logger.info(
                f"[MCP:search] query='{query}' | limit={limit} | collection='{collection_name}'"
            )

            token_to_verify = token
            if not token_to_verify and ctx:
                try:
                    if hasattr(ctx, "request_context") and ctx.request_context:
                        req = getattr(ctx.request_context, "request", None)
                        if req and hasattr(req, "headers"):
                            token_to_verify = req.headers.get("authorization") or req.headers.get("x-authorization")
                except Exception as exc:
                    logger.debug(f"[MCP:auth] Error extracting header from context: {exc}")

            is_authorized, reason = verify_collection_access(token_to_verify, collection_name)
            if not is_authorized:
                logger.warning(
                    f"[MCP:auth] Access DENIED for collection '{collection_name}': {reason}"
                )
                return json.dumps(
                    {
                        "status": "unauthorized",
                        "error": reason,
                        "collection": collection_name,
                    },
                    ensure_ascii=False,
                    indent=2,
                )

            try:
                service = get_milvus_service()

                raw_results = service.search(
                    query=query,
                    collection_name=collection_name,
                    limit=limit,
                )

                results: list[dict[str, Any]] = [
                    {
                        "rank": rank,
                        "score": round(hit.get("score") or 0.0, 6),
                        "title": hit.get("title", "Untitled"),
                        "url": hit.get("url", ""),
                        "chunk_index": hit.get("chunk_index", 0),
                        "text": (hit.get("text") or "")
                    }
                    for rank, hit in enumerate(raw_results, start=1)
                ]

                logger.info(f"[MCP:search] Returned {len(results)} result(s).")

                return json.dumps(
                    {
                        "query": query,
                        "collection": collection_name,
                        "total_results": len(results),
                        "results": results,
                    },
                    ensure_ascii=False,
                    indent=2,
                )

            except Exception as exc:
                logger.error(f"[MCP:search] search_notion_docs failed: {exc}")
                return json.dumps(
                    {"error": str(exc), "query": query, "collection": collection_name},
                    ensure_ascii=False,
                )

