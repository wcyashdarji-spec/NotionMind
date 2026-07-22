from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.utils.schemas import SearchRequest
from src.services.milvus_service import MilvusService
from src.config import MILVUS_COLLECTION_NAME, MILVUS_ENDPOINT, MILVUS_TOKEN, logger

router = APIRouter(prefix="/api", tags=["Search"])


@router.post(
    "/search",
    summary="Hybrid vector search",
    response_description="Ranked list of matching document chunks.",
)
async def search(request: SearchRequest) -> dict:
    """
    Query the vector database using dense semantic and sparse BM25 signals.

    Results are merged and reranked via Reciprocal Rank Fusion (RRF).

    Args:
        request: Validated :class:`SearchRequest` body.

    Returns:
        JSON object with ``query``, ``collection_name``, ``results_count``,
        and ``results`` (list of chunk dicts with ``score``, ``title``,
        ``url``, ``text``, and ``chunk_index``).

    Raises:
        HTTPException 400: When Milvus credentials are not configured.
        HTTPException 500: On any unexpected search error.
    """
    if not MILVUS_ENDPOINT or not MILVUS_TOKEN:
        logger.error("Search aborted: Milvus credentials are not configured.")
        raise HTTPException(status_code=400, detail="Milvus credentials are not configured.")

    collection = request.collection_name or MILVUS_COLLECTION_NAME

    try:
        milvus = MilvusService(uri=MILVUS_ENDPOINT, token=MILVUS_TOKEN)
        results = await milvus.search(
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

