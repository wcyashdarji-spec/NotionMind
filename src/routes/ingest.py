from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.config import (
    MILVUS_COLLECTION_NAME,
    MILVUS_ENDPOINT,
    MILVUS_TOKEN,
    NOTION_TOKEN,
    logger,
)
from src.services.milvus_service import MilvusService
from src.services.notion_service import NotionService
from src.database import get_db, list_ingestion_records, upsert_ingestion_record
from src.utils.schemas import IngestRequest, IngestResponse, UpdateRequest, UpdateResponse

router = APIRouter(prefix="/api", tags=["Ingestion"])


@router.post(
    "/ingest",
    summary="Ingest Notion pages into Milvus",
    response_model=IngestResponse,
    response_description="Summary of the ingestion run and database record.",
)
def ingest(request: IngestRequest, db: Session = Depends(get_db)) -> IngestResponse:
    """
    Crawl Notion pages and insert them as vector chunks into Milvus,
    saving or updating the metadata entry in PostgreSQL.

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

        db_record = upsert_ingestion_record(
            db=db,
            collection_name=collection,
            root_id=request.root_id,
            pages_ingested=len(documents),
            vector_chunks_created=total_chunks,
            status="success",
        )

        return IngestResponse(
            status="success",
            root_id=db_record.root_id,
            collection_name=db_record.collection_name,
            pages_ingested=db_record.pages_ingested,
            vector_chunks_created=db_record.vector_chunks_created,
            created_at=db_record.created_at.isoformat() if db_record.created_at else None,
            updated_at=db_record.updated_at.isoformat() if db_record.updated_at else None,
        )

    except Exception as exc:
        logger.exception(f"Ingestion failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/update",
    summary="Update collection content",
    response_model=UpdateResponse,
    response_description="Summary of the collection content update run and database record.",
)
def update_collection(request: UpdateRequest, db: Session = Depends(get_db)) -> UpdateResponse:
    """
    Update collection content by re-crawling Notion and replacing collection data.

    This endpoint removes prior collection content and ingests updated Notion data
    for the specified root_id or workspace.

    Args:
        request: Validated :class:`UpdateRequest` body.

    Returns:
        :class:`UpdateResponse` containing update details and chunk count.

    Raises:
        HTTPException 400: When required environment variables are missing.
        HTTPException 500: On any unexpected error during update.
    """
    if not NOTION_TOKEN:
        logger.error("Collection update aborted: NOTION_TOKEN is not configured.")
        raise HTTPException(status_code=400, detail="NOTION_TOKEN is not configured.")

    if not MILVUS_ENDPOINT or not MILVUS_TOKEN:
        logger.error("Collection update aborted: Milvus credentials are not configured.")
        raise HTTPException(status_code=400, detail="Milvus credentials are not configured.")

    collection = request.collection_name or MILVUS_COLLECTION_NAME
    logger.info(
        f"Collection update started – collection='{collection}', root_id={request.root_id}, "
        f"chunk_size={request.chunk_size}, chunk_overlap={request.chunk_overlap}."
    )

    try:
        notion = NotionService(token=NOTION_TOKEN)
        milvus = MilvusService(uri=MILVUS_ENDPOINT, token=MILVUS_TOKEN)

        if request.root_id:
            logger.info(f"Crawling root_id={request.root_id} for collection update …")
            documents = notion.crawl(request.root_id)
        else:
            logger.info("No root_id provided – crawling workspace for collection update …")
            documents = notion.fetch_workspace()

        logger.info(f"Crawl complete – {len(documents)} page(s) discovered for update.")

        total_chunks = milvus.ingest(
            documents=documents,
            collection_name=collection,
            recreate=True,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
        )

        db_record = upsert_ingestion_record(
            db=db,
            collection_name=collection,
            root_id=request.root_id,
            pages_ingested=len(documents),
            vector_chunks_created=total_chunks,
            status="success",
        )

        return UpdateResponse(
            status="success",
            root_id=db_record.root_id,
            pages_ingested=db_record.pages_ingested,
            vector_chunks_created=db_record.vector_chunks_created,
            collection_name=db_record.collection_name,
            message=f"Successfully updated collection '{collection}' with {len(documents)} page(s) and {total_chunks} chunk(s).",
            created_at=db_record.created_at.isoformat() if db_record.created_at else None,
            updated_at=db_record.updated_at.isoformat() if db_record.updated_at else None,
        )

    except Exception as exc:
        logger.exception(f"Collection update failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/records",
    summary="Get all database ingestion records",
    response_description="List of ingestion metadata records stored in PostgreSQL.",
)
def get_records(db: Session = Depends(get_db)) -> list[dict]:
    """Retrieve all database ingestion records tracked in PostgreSQL."""
    records = list_ingestion_records(db)
    return [rec.to_dict() for rec in records]



