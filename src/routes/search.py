from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.utils.schemas import SearchRequest
from src.services.chroma_service import ChromaService
from src.config import CHROMA_COLLECTION_NAME, CHROMA_DB_PATH, logger
from src.utils.deps import get_current_token

router = APIRouter(prefix="/api", tags=["Search"])


@router.post(
    "/search",
    summary="Hybrid vector search",
    response_description="Ranked list of matching document chunks.",
)
async def search(
    request: SearchRequest,
    _token: dict = Depends(get_current_token),
) -> dict:
    """
    Query the vector database using dense semantic and sparse BM25 signals.

    Results are merged and reranked via Reciprocal Rank Fusion (RRF).

    Args:
        request: Validated :class:`SearchRequest` body.

    Returns:
        JSON object with ``query``, ``collection_name``, ``results_count``,
        and ``results`` (list of unified hits containing text chunks and/or image metadata,
        differentiated by the ``type`` key: ``"text"`` or ``"image"``).

    Raises:
        HTTPException 400: When Milvus credentials are not configured.
        HTTPException 500: On any unexpected search error.
    """
    collection = request.collection_name or CHROMA_COLLECTION_NAME

    try:
        chroma = ChromaService(db_path=CHROMA_DB_PATH)
        results = await chroma.search(
            query=request.query,
            collection_name=collection,
            limit=request.limit,
        )
        return {
            "query": request.query,
            "collection_name": collection,
            "results_count": len(results),
            "results": results,
        }

    except Exception as exc:
        logger.exception(f"Search failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

