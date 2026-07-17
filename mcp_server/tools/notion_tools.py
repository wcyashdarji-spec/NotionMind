from __future__ import annotations

import json
from typing import Annotated, Any

from pydantic import Field
from fastmcp import FastMCP, Context

from mcp_server.server import get_milvus_service
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
            ctx: Context = None,
        ) -> str:
            """
            Search indexed Notion pages using hybrid semantic + BM25 retrieval.

            Sends the query to the Milvus hybrid search engine, which runs a dense
            COSINE vector search and a sparse BM25 keyword search simultaneously.
            Both result sets are merged using Reciprocal Rank Fusion (k=60) and the
            top-ranked chunks are returned as a JSON string.

            Args:
                query: Natural-language question or keyword phrase to search for.
                limit: Number of chunks to return (1–20, default 5).
                collection_name: Target Milvus collection name.

            Returns:
                A JSON-formatted string with the following structure::

                    {
                    "query": "<original query>",
                    "collection": "<collection name>",
                    "total_results": <int>,
                    "results": [
                        {
                        "rank": 1,
                        "score": 0.032,
                        "title": "Product Q&A",
                        "url": "https://app.notion.com/p/...",
                        "chunk_index": 0,
                        "text": "..."
                        },
                        ...
                    ]
                    }

            Raises:
                ValueError: When the collection does not exist in Milvus.
                RuntimeError: When Milvus credentials are not configured.
            """
            logger.info(
                f"[MCP:search] query='{query}' | limit={limit} | collection='{collection_name}'"
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

