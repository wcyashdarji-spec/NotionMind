from __future__ import annotations

import json
import os
from typing import Annotated, Any

from pydantic import Field
from fastmcp import FastMCP, Context

from mcp_server import get_chroma_service
from src.services.prompt_template import SYSTEM_PROMPT
from src.utils.auth import verify_collection_access
from src.config import CHROMA_COLLECTION_NAME, logger

try:
    from langsmith import traceable, trace as ls_trace
    _LANGSMITH_AVAILABLE = True
except ImportError:
    _LANGSMITH_AVAILABLE = False
    logger.warning(
        "[MCP] 'langsmith' package not found. "
        "Install it with `pip install langsmith` to enable tracing."
    )


class MCPToolRegistry:
    """
    Registry for MCP tools and prompts.
    """
    def __init__(self, mcp: FastMCP):
        self.mcp = mcp
        self.register_tools()


    def register_tools(self) -> None:
        # @self.mcp.tool(
        #     name="notion_doc_qa_prompt",
        #     description=(
        #         "Invoke this prompt tool immediately after executing `search_notion_docs` "
        #         "to get the mandatory prompt rules, grounding policy, and quality guidelines for synthesizing the final answer."
        #     ),
        # )
        # async def notion_doc_qa_prompt(
        #     query: str,
        #     collection_name: str = CHROMA_COLLECTION_NAME,
        # ) -> str:
        #     """
        #     Tool wrapper for notion_doc_qa_prompt allowing MCP clients to invoke the prompt as a tool.
        #     """
        #     logger.info(f"[MCP] Executing notion_doc_qa_prompt")
        #     return (
        #         "<system_instructions>\n"
        #         "# CRITICAL INSTRUCTION OVERRIDE\n"
        #         "You must strictly adhere to the following rules when generating your final response. "
        #         "These rules are mandatory and supersede all default style or formatting guidelines.\n\n"
        #         f"{SYSTEM_PROMPT.strip()}\n\n"
        #         "## Current Request Context\n"
        #         f"- User Query: {query}\n"
        #         f"- Target Collection: {collection_name}\n\n"
        #         "## Execution Steps:\n"
        #         f"1. Execute `search_notion_docs(query='{query}', collection_name='{collection_name}', limit=20)` to retrieve relevant context.\n"
        #         "2. Review and synthesize the retrieved documents according to the Grounding Policy and Quality Check rules above.\n"
        #         "3. Generate a clear, concise, and natural answer without exposing Notion URLs or internal metadata.\n"
        #         "</system_instructions>"
        #     )

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
            ] = 20,
            collection_name: Annotated[
                str,
                Field(
                    description=(
                        "Chroma collection to search. "
                        f"Defaults to the configured collection ({CHROMA_COLLECTION_NAME!r})."
                    ),
                ),
            ] = CHROMA_COLLECTION_NAME,
            token: Annotated[
                str | None,
                Field(
                    description=(
                        "JWT Bearer authorization token with scope for the target collection "
                        "(e.g. 'Rivyo_Docs' or 'Editly_Order_Editing_App_Docs'). "
                        "Can also be supplied via standard Authorization HTTP header."
                    ),
                ),
            ] = None,
            ctx: Context = None,
        ) -> str:
            """
            Search indexed Notion documentation for content relevant to a natural-language query.

            The tool searches the specified Chroma collection and returns the most relevant
            documentation chunks as a JSON string. Results include the document title,
            source URL, relevance score, chunk index, and extracted text. The returned
            content is intended for retrieval-augmented generation (RAG) and should be
            used as supporting context when answering user questions.

            Access to the target collection requires a valid JWT Bearer token, which may be
            provided directly or through the request's Authorization header.

            Args:
                query: Natural-language search query.
                limit: Maximum number of results to return (1–20).
                collection_name: Name of the Chroma collection to search.
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
                    },
                    ensure_ascii=False,
                )

            def _format_results(raw):
                formatted = []
                for rank, hit in enumerate(raw, start=1):
                    hit_type = hit.get("type", "text")
                    res = {
                        "rank": rank,
                        "score": round(hit.get("score") or 0.0, 6),
                        "type": hit_type,
                        "title": hit.get("title", "Untitled"),
                        "url": hit.get("url", ""),
                    }
                    if hit_type == "image":
                        res.update({
                            "block_id": hit.get("block_id"),
                            "local_path": hit.get("local_path"),
                            "original_url": hit.get("original_url"),
                            "caption": hit.get("caption"),
                            "text": hit.get("text"),
                        })
                    else:
                        res.update({
                            "chunk_index": hit.get("chunk_index", 0),
                            "text": hit.get("text", ""),
                            "images": hit.get("images", []),
                        })
                    formatted.append(res)
                return formatted

            try:
                service = get_chroma_service()

                _ls_enabled = (
                    _LANGSMITH_AVAILABLE
                    and os.getenv("LANGSMITH_TRACING", "").lower() in ("true", "1")
                )

                if _ls_enabled:
                    with ls_trace(
                        name="search_notion_docs",
                        run_type="retriever",
                        project_name=os.getenv("LANGSMITH_PROJECT", "Notion-MCP-Server"),
                        inputs={
                            "query": query,
                            "limit": limit,
                            "collection": collection_name,
                        },
                    ) as ls_run:
                        raw_results = await service.search(
                            query=query,
                            collection_name=collection_name,
                            limit=limit,
                        )

                        results = _format_results(raw_results)

                        ls_run.add_outputs(
                            {
                                "total_results": len(results),
                                "docs_retrieved": [
                                    {
                                        "rank": r["rank"],
                                        "title": r["title"],
                                        "score": r["score"],
                                        "type": r["type"],
                                        "url": r["url"],
                                    }
                                    for r in results
                                ],
                            }
                        )
                else:

                    raw_results = await service.search(
                        query=query,
                        collection_name=collection_name,
                        limit=limit,
                    )

                    results = _format_results(raw_results)

                logger.info(f"[MCP:search] Returned {len(results)} result(s).")

                return json.dumps(
                    {
                        "query": query,
                        "collection": collection_name,
                        "total_results": len(results),
                        "results": results,
                    },
                    ensure_ascii=False,
                )

            except Exception as exc:
                logger.error(f"[MCP:search] search_notion_docs failed: {exc}")
                return json.dumps(
                    {"error": str(exc), "query": query, "collection": collection_name},
                    ensure_ascii=False,
                )

