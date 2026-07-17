from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.config import (
    MILVUS_COLLECTION_NAME,
    MILVUS_ENDPOINT,
    MILVUS_TOKEN,
    NOTION_TOKEN,
    logger,
)
from src.utils.schemas import IngestRequest
from src.services.milvus_service import MilvusService
from src.services.notion_service import NotionService

router = APIRouter(prefix="/api", tags=["Ingestion"])


@router.post(
    "/ingest",
    summary="Ingest Notion pages into Milvus",
    response_description="Summary of the ingestion run.",
)
def ingest(request: IngestRequest) -> dict:
    """
    Crawl Notion pages and insert them as vector chunks into Milvus.

    The crawler starts at *root_id* when supplied, otherwise it discovers all
    root-level pages that the integration token can access.

    Args:
        request: Validated :class:`IngestRequest` body.

    Returns:
        JSON object with ``pages_ingested``, ``vector_chunks_created``, and
        ``collection_name``.

    Raises:
        HTTPException 400: When required environment variables are missing.
        HTTPException 500: On any unexpected ingestion error.
    """
    if not NOTION_TOKEN:
        logger.error("Ingestion aborted: NOTION_TOKEN is not configured.")
        raise HTTPException(status_code=400, detail="NOTION_TOKEN is not configured.")

    if not MILVUS_ENDPOINT or not MILVUS_TOKEN:
        logger.error("Ingestion aborted: Milvus credentials are not configured.")
        raise HTTPException(status_code=400, detail="Milvus credentials are not configured.")

    collection = request.collection_name or MILVUS_COLLECTION_NAME
    logger.info(f"Ingestion started – collection='{collection}', recreate={request.recreate}.")

    try:
        notion = NotionService(token=NOTION_TOKEN)
        milvus = MilvusService(uri=MILVUS_ENDPOINT, token=MILVUS_TOKEN)

        if request.root_id:
            logger.info(f"Crawling from root_id={request.root_id} …")
            documents = notion.crawl(request.root_id)
        else:
            logger.info("No root_id provided – crawling entire workspace …")
            documents = notion.fetch_workspace()

        logger.info(f"Crawl complete – {len(documents)} page(s) discovered.")

        total_chunks = milvus.ingest(
            documents=documents,
            collection_name=collection,
            recreate=request.recreate,
        )

        return {
            "status": "success",
            "pages_ingested": len(documents),
            "vector_chunks_created": total_chunks,
            "collection_name": collection,
        }

    except Exception as exc:
        logger.exception(f"Ingestion failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

