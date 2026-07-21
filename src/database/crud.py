from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from src.config import logger
from src.database.models import IngestionRecord, utc_now


def upsert_ingestion_record(
    db: Session,
    collection_name: str,
    root_id: Optional[str] = None,
    pages_ingested: int = 0,
    vector_chunks_created: int = 0,
    status: str = "success",
) -> IngestionRecord:
    """
    Create or update an ingestion record for a collection.

    This function maintains a single ingestion record per collection.
    If a record already exists, it updates the ingestion metadata while
    preserving the original creation timestamp. Otherwise, it inserts
    a new record.

    Args:
        db: Active SQLAlchemy database session.
        collection_name: Unique collection identifier.
        root_id: Root Notion page ID associated with the collection.
        pages_ingested: Number of Notion pages processed.
        vector_chunks_created: Number of vector chunks generated.
        status: Current ingestion status (e.g. "success", "failed").

    Returns:
        The newly created or updated ``IngestionRecord``.

    Raises:
        Exception: Re-raises any database exception after rolling back
            the active transaction.
    """
    try:
        record = (
            db.query(IngestionRecord)
            .filter(IngestionRecord.collection_name == collection_name)
            .first()
        )

        now = utc_now()

        if record:
            logger.info(f"Updating existing database entry for collection '{collection_name}'.")
            if root_id is not None:
                record.root_id = root_id
            record.pages_ingested = pages_ingested
            record.vector_chunks_created = vector_chunks_created
            record.status = status
            record.updated_at = now
        else:
            logger.info(f"Creating new database entry for collection '{collection_name}'.")
            record = IngestionRecord(
                root_id=root_id,
                collection_name=collection_name,
                pages_ingested=pages_ingested,
                vector_chunks_created=vector_chunks_created,
                status=status,
                created_at=now,
                updated_at=now,
            )
            db.add(record)

        db.commit()
        db.refresh(record)
        return record
    
    except Exception as exc:
        db.rollback()
        logger.error(f"Error upserting ingestion record for '{collection_name}': {exc}")
        raise exc


def get_ingestion_record_by_collection(
    db: Session,
    collection_name: str,
) -> Optional[IngestionRecord]:
    """
    Retrieve the ingestion record for a collection.

    Args:
        db: Active SQLAlchemy database session.
        collection_name: Collection identifier.

    Returns:
        The matching ``IngestionRecord`` if one exists; otherwise ``None``.
    """
    return (
        db.query(IngestionRecord)
        .filter(IngestionRecord.collection_name == collection_name)
        .first()
    )


def list_ingestion_records(
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> List[IngestionRecord]:
    """
    Retrieve ingestion records ordered by the most recent update.

    Args:
        db: Active SQLAlchemy database session.
        skip: Number of records to skip for pagination.
        limit: Maximum number of records to return.

    Returns:
        A list of ingestion records sorted by ``updated_at`` in
        descending order.
    """
    return (
        db.query(IngestionRecord)
        .order_by(IngestionRecord.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )