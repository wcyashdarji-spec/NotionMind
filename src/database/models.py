from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String

from src.database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IngestionRecord(Base):
    """
    SQLAlchemy model representing vector database ingestion / collection metadata records.
    Tracks root_id, collection_name, status, chunk counts, created_at, and updated_at timestamps.
    """

    __tablename__ = "ingestion_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    root_id = Column(String(255), nullable=True, index=True)
    collection_name = Column(String(255), nullable=False, unique=True, index=True)
    pages_ingested = Column(Integer, default=0)
    vector_chunks_created = Column(Integer, default=0)
    status = Column(String(50), default="success")

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    def to_dict(self) -> dict:
        """Convert ORM model instance to dictionary representation."""
        return {
            "id": self.id,
            "root_id": self.root_id,
            "collection_name": self.collection_name,
            "pages_ingested": self.pages_ingested,
            "vector_chunks_created": self.vector_chunks_created,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
