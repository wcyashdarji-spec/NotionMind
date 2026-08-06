from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from src.config import logger
from src.database.models import IngestionRecord, RevokedToken, User, utc_now


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


def create_user(db: Session, email: str, hashed_password: str) -> User:
    """
    Persist a new user account to the database.

    Args:
        db: Active SQLAlchemy database session.
        email: Unique e-mail address for the new account.
        hashed_password: Bcrypt-hashed password string.

    Returns:
        The newly created ``User`` ORM instance.

    Raises:
        Exception: Re-raises any database exception after rollback.
    """
    try:
        user = User(email=email, hashed_password=hashed_password)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created new user account: {email}")
        return user
    except Exception as exc:
        db.rollback()
        logger.error(f"Error creating user '{email}': {exc}")
        raise exc


def get_user_by_email(db: Session, email: str) -> User | None:
    """
    Look up a user by their e-mail address.

    Args:
        db: Active SQLAlchemy database session.
        email: E-mail address to search for.

    Returns:
        Matching ``User`` instance, or ``None`` if not found.
    """
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """
    Look up a user by their primary-key ID.

    Args:
        db: Active SQLAlchemy database session.
        user_id: Integer primary key.

    Returns:
        Matching ``User`` instance, or ``None`` if not found.
    """
    return db.query(User).filter(User.id == user_id).first()


def revoke_token(db: Session, jti: str, expires_at: datetime) -> RevokedToken:
    """
    Add a JWT's ``jti`` claim to the revocation blacklist.

    Called during logout to prevent the token from being reused
    until it naturally expires.

    Args:
        db: Active SQLAlchemy database session.
        jti: The unique JWT ID claim from the token payload.
        expires_at: The token's original expiration datetime (UTC).

    Returns:
        The persisted ``RevokedToken`` instance.

    Raises:
        Exception: Re-raises any database exception after rollback.
    """
    try:
        revoked = RevokedToken(jti=jti, expires_at=expires_at)
        db.add(revoked)
        db.commit()
        db.refresh(revoked)
        logger.info(f"Token revoked – jti={jti}")
        return revoked
    except Exception as exc:
        db.rollback()
        logger.error(f"Error revoking token jti={jti}: {exc}")
        raise exc


def is_token_revoked(db: Session, jti: str) -> bool:
    """
    Check whether a JWT has been blacklisted (logged out).

    Args:
        db: Active SQLAlchemy database session.
        jti: The unique JWT ID claim to look up.

    Returns:
        ``True`` if the token has been revoked; ``False`` otherwise.
    """
    return db.query(RevokedToken).filter(RevokedToken.jti == jti).first() is not None


def delete_ingestion_record(db: Session, collection_name: str) -> bool:
    """
    Delete the ingestion record for a collection from the database.

    Args:
        db: Active SQLAlchemy database session.
        collection_name: Collection identifier.

    Returns:
        ``True`` if the record was successfully found and deleted; ``False`` otherwise.

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
        if record:
            logger.info(f"Deleting database entry for collection '{collection_name}'.")
            db.delete(record)
            db.commit()
            return True
        return False
    except Exception as exc:
        db.rollback()
        logger.error(f"Error deleting ingestion record for '{collection_name}': {exc}")
        raise exc


