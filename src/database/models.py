from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Integer, String

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


class User(Base):
    """
    SQLAlchemy model representing an authenticated user account.
    Stores email, bcrypt-hashed password, and account status.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    def to_dict(self) -> dict:
        """Convert ORM model instance to a safe dictionary (no password)."""
        return {
            "id": self.id,
            "email": self.email,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class RevokedToken(Base):
    """
    JWT token blacklist for logout support.
    Each revoked token's `jti` claim is stored here. The `get_current_token`
    dependency checks this table and returns 401 for any blacklisted jti.
    Rows whose `expires_at` has passed can be pruned safely.
    """

    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    jti = Column(String(64), nullable=False, unique=True, index=True)
    revoked_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class GeneratedToken(Base):
    """
    SQLAlchemy model representing a generated token with metadata.
    Stores the encoded token, collection scope, duration, validity status, and timestamps.
    """

    __tablename__ = "generated_tokens"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    token = Column(String, nullable=False, index=True)
    collection_name = Column(String(255), nullable=False, index=True)
    duration_days = Column(Integer, nullable=False)
    is_valid = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
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
            "token": self.token,
            "collection_name": self.collection_name,
            "duration_days": self.duration_days,
            "is_valid": self.is_valid,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

