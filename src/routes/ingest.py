from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DB_PATH,
    NOTION_TOKEN,
    logger,
)
from src.utils.deps import get_current_token
from src.services.chroma_service import ChromaService
from src.services.notion_service import NotionService
from src.database import get_db, list_ingestion_records, upsert_ingestion_record, delete_ingestion_record, IngestionRecord
from src.utils.schemas import IngestRequest, IngestResponse, UpdateRequest, UpdateResponse, UpdateAllRequest, UpdateAllResponse, DeleteCollectionResponse

router = APIRouter(prefix="/api", tags=["Ingestion"])


@router.post(
    "/ingest",
    summary="Ingest Notion pages into Milvus",
    response_model=IngestResponse,
    response_description="Summary of the ingestion run and database record.",
)
async def ingest(
    request: IngestRequest,
    db: Session = Depends(get_db),
    _token: dict = Depends(get_current_token),
) -> IngestResponse:
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

    collection = request.collection_name or CHROMA_COLLECTION_NAME
    logger.info(f"Ingestion started – collection='{collection}', recreate={request.recreate}.")

    try:
        async with NotionService(token=NOTION_TOKEN) as notion:
            chroma = ChromaService(db_path=CHROMA_DB_PATH)

            if request.root_id:
                logger.info(f"Crawling from root_id={request.root_id} …")
                documents = await notion.crawl(request.root_id)
            else:
                logger.info("No root_id provided – crawling entire workspace …")
                documents = await notion.fetch_workspace()

            logger.info(f"Crawl complete – {len(documents)} page(s) discovered.")

            total_chunks = await chroma.ingest(
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
async def update_collection(
    request: UpdateRequest,
    db: Session = Depends(get_db),
    _token: dict = Depends(get_current_token),
) -> UpdateResponse:
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

    collection = request.collection_name or CHROMA_COLLECTION_NAME
    logger.info(
        f"Collection update started – collection='{collection}', root_id={request.root_id}, "
        f"chunk_size={request.chunk_size}, chunk_overlap={request.chunk_overlap}."
    )

    try:
        async with NotionService(token=NOTION_TOKEN) as notion:
            chroma = ChromaService(db_path=CHROMA_DB_PATH)

            if request.root_id:
                logger.info(f"Crawling root_id={request.root_id} for collection update …")
                documents = await notion.crawl(request.root_id)
            else:
                logger.info("No root_id provided – crawling workspace for collection update …")
                documents = await notion.fetch_workspace()

            logger.info(f"Crawl complete – {len(documents)} page(s) discovered for update.")

            total_chunks = await chroma.ingest(
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
async def get_records(
    db: Session = Depends(get_db),
    _token: dict = Depends(get_current_token),
) -> list[dict]:
    """Retrieve all database ingestion records tracked in PostgreSQL."""
    records = list_ingestion_records(db)
    return [rec.to_dict() for rec in records]


@router.post(
    "/update-all",
    summary="Update all collection contents from the database",
    response_model=UpdateAllResponse,
    response_description="Summary of the bulk update run across all collections.",
)
async def update_all_collections(
    request: UpdateAllRequest,
    db: Session = Depends(get_db),
    _token: dict = Depends(get_current_token),
) -> UpdateAllResponse:
    """
    Update all registered Notion collections.

    This endpoint retrieves every registered collection from the ingestion
    metadata table, crawls the latest content from Notion, recreates the
    corresponding Milvus collection, and updates the ingestion statistics.

    Collection updates are processed independently. If one collection fails,
    the failure is recorded while the remaining collections continue to be
    processed.

    Args:
        request: Chunking configuration used during vector ingestion.
        db: Active SQLAlchemy database session.

    Returns:
        A summary containing the update status for every registered
        collection.

    Raises:
        HTTPException:
            - 400 if the required Notion or Milvus configuration is missing.
            - 500 if ingestion records cannot be retrieved from the database.
    """
    if not NOTION_TOKEN:
        logger.error("Bulk update aborted: NOTION_TOKEN is not configured.")
        raise HTTPException(status_code=400, detail="NOTION_TOKEN is not configured.")



    try:
        records = db.query(IngestionRecord).all()
    except Exception as exc:
        logger.exception(f"Failed to query ingestion records: {exc}")
        raise HTTPException(status_code=500, detail=f"Database query failed: {exc}")

    if not records:
        logger.info("No ingestion records found in database. Nothing to update.")
        return UpdateAllResponse(
            status="success",
            updated_collections=[],
            message="No registered collections found to update."
        )

    logger.info(f"Starting bulk collection update for {len(records)} record(s).")
    updated_list = []
    has_failure = False
    has_success = False

    async with NotionService(token=NOTION_TOKEN) as notion:
        chroma = ChromaService(db_path=CHROMA_DB_PATH)

        for record in records:
            collection = record.collection_name
            root_id = record.root_id
            logger.info(f"Processing update for collection '{collection}' (root_id: {root_id}).")

            try:
                if root_id:
                    logger.info(f"Crawling root_id={root_id} for collection '{collection}' update …")
                    documents = await notion.crawl(root_id)
                else:
                    logger.info(f"No root_id for collection '{collection}' – crawling entire workspace …")
                    documents = await notion.fetch_workspace()

                logger.info(f"Crawl complete for '{collection}' – {len(documents)} page(s) discovered.")

                total_chunks = await chroma.ingest(
                    documents=documents,
                    collection_name=collection,
                    recreate=True,
                    chunk_size=request.chunk_size,
                    chunk_overlap=request.chunk_overlap,
                )

                db_record = upsert_ingestion_record(
                    db=db,
                    collection_name=collection,
                    root_id=root_id,
                    pages_ingested=len(documents),
                    vector_chunks_created=total_chunks,
                    status="success",
                )

                updated_list.append(
                    UpdateResponse(
                        status="success",
                        root_id=db_record.root_id,
                        pages_ingested=db_record.pages_ingested,
                        vector_chunks_created=db_record.vector_chunks_created,
                        collection_name=db_record.collection_name,
                        message=f"Successfully updated collection '{collection}' with {len(documents)} page(s) and {total_chunks} chunk(s).",
                        created_at=db_record.created_at.isoformat() if db_record.created_at else None,
                        updated_at=db_record.updated_at.isoformat() if db_record.updated_at else None,
                    )
                )
                has_success = True

            except Exception as exc:
                logger.exception(f"Collection update failed for '{collection}': {exc}")
                has_failure = True

                try:
                    db_record = upsert_ingestion_record(
                        db=db,
                        collection_name=collection,
                        root_id=root_id,
                        pages_ingested=record.pages_ingested or 0,
                        vector_chunks_created=record.vector_chunks_created or 0,
                        status="failed",
                    )
                    created_at_str = db_record.created_at.isoformat() if db_record.created_at else None
                    updated_at_str = db_record.updated_at.isoformat() if db_record.updated_at else None
                except Exception as db_exc:
                    logger.error(f"Failed to update failed status in database for '{collection}': {db_exc}")
                    created_at_str = record.created_at.isoformat() if getattr(record, "created_at", None) else None
                    updated_at_str = record.updated_at.isoformat() if getattr(record, "updated_at", None) else None

                updated_list.append(
                    UpdateResponse(
                        status="failed",
                        root_id=root_id,
                        pages_ingested=0,
                        vector_chunks_created=0,
                        collection_name=collection,
                        message=f"Update failed: {exc}",
                        created_at=created_at_str,
                        updated_at=updated_at_str,
                    )
                )

    if has_success and has_failure:
        overall_status = "partial_failure"
        msg = f"Completed bulk update with errors. Updated {len(records)} collections."
    elif has_failure:
        overall_status = "failed"
        msg = "All collection updates failed."
    else:
        overall_status = "success"
        msg = f"Successfully updated all {len(records)} collections."

    return UpdateAllResponse(
        status=overall_status,
        updated_collections=updated_list,
        message=msg,
    )


@router.delete(
    "/collection/{collection_name}",
    summary="Delete collection and all relevant data",
    response_model=DeleteCollectionResponse,
    response_description="Confirmation of collection and chunk deletion.",
)
async def delete_collection(
    collection_name: str,
    db: Session = Depends(get_db),
    _token: dict = Depends(get_current_token),
) -> DeleteCollectionResponse:
    """
    Delete a collection and all associated data, including chunks stored in the vector database,
    local image assets downloaded, and metadata records in PostgreSQL.

    Args:
        collection_name: Name of the collection to delete.

    Returns:
        A response confirming the deletion stats.
    """
    logger.info(f"Collection deletion requested – collection='{collection_name}'.")

    try:
        # 1. Delete from Vector DB (ChromaDB)
        chroma = ChromaService(db_path=CHROMA_DB_PATH)
        delete_stats = await chroma.delete_collection(collection_name)

        # 2. Delete from database (SQLAlchemy)
        deleted_from_db = delete_ingestion_record(db=db, collection_name=collection_name)

        if not deleted_from_db and delete_stats["chunks_deleted"] == 0:
            logger.warning(f"No collection or ingestion record found for '{collection_name}'.")
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{collection_name}' not found."
            )

        msg = (
            f"Successfully deleted collection '{collection_name}'. "
            f"Deleted {delete_stats['chunks_deleted']} chunk(s) from ChromaDB, "
            f"{delete_stats['images_deleted']} downloaded image(s), "
            f"and metadata record from database."
        )
        logger.info(msg)

        return DeleteCollectionResponse(
            status="success",
            collection_name=collection_name,
            message=msg,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to delete collection '{collection_name}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))





