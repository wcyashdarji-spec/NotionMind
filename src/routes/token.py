from __future__ import annotations

from typing import List
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status

from src.config import logger
from src.database.connection import get_db
from src.utils.deps import get_current_user
from src.utils.auth import generate_access_token
from src.utils.token_crypto import decode_token_str
from src.database.models import User, IngestionRecord
from src.database.crud import create_generated_token, get_generated_tokens
from src.utils.schemas import TokenGenerateRequest, TokenGenerateResponse, TokenListItem

router = APIRouter(prefix="/api/token", tags=["Token"])


@router.post(
    "/generate",
    response_model=TokenGenerateResponse,
    summary="Generate and store a new collection access token",
)
def generate_token(
    request: TokenGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TokenGenerateResponse:
    """
    Generate a new access token for a collection.

    This endpoint creates a bearer token for the specified collection,
    invalidates any previously active tokens for the same collection,
    stores the new token with its expiration details, and returns the
    generated plain-text token to the client.

    Raises:
        HTTPException:
            - 400: If the collection name is empty or the requested
              token duration is invalid.
            - 500: If an unexpected error occurs while generating or
              storing the token.
    """
    try:
        if request.expires_days not in [30, 60, 90]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token duration must be exactly 30, 60, or 90 days.",
            )

        col_name = request.collection_name.strip()
        if not col_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Collection name cannot be empty.",
            )

        plain_token = generate_access_token(
            collections=[col_name],
            expires_days=request.expires_days,
        )

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=request.expires_days)

        db_token = create_generated_token(
            db=db,
            token=plain_token,
            collection_name=col_name,
            duration_days=request.expires_days,
            expires_at=expires_at,
        )

        return TokenGenerateResponse(
            id=db_token.id,
            token=plain_token,
            collection_name=db_token.collection_name,
            duration_days=db_token.duration_days,
            is_valid=db_token.is_valid,
            created_at=db_token.created_at.isoformat(),
            expires_at=db_token.expires_at.isoformat(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error generating token for collection '{request.collection_name}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error while generating token",
        )


@router.get(
    "/list",
    response_model=List[TokenListItem],
    summary="List all generated tokens and their status",
)
def list_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[TokenListItem]:
    """
    Retrieve all generated collection access tokens.

    This endpoint returns the complete history of generated tokens,
    including their associated collection, validity status, creation
    time, expiration time, and decoded plain-text token value for
    administrative use.

    Raises:
        HTTPException:
            - 500: If an unexpected error occurs while retrieving the
              generated tokens.
    """
    try:
        tokens = get_generated_tokens(db)
        results = []
        for t in tokens:
            try:
                plain_token = decode_token_str(t.token)
            except Exception:
                plain_token = "Decryption/Decoding failed"

            results.append(
                TokenListItem(
                    id=t.id,
                    token=plain_token,
                    collection_name=t.collection_name,
                    duration_days=t.duration_days,
                    is_valid=t.is_valid,
                    created_at=t.created_at.isoformat(),
                    expires_at=t.expires_at.isoformat(),
                )
            )
        return results
    except Exception as exc:
        logger.error(f"Error retrieving generated tokens: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving tokens",
        )


@router.get(
    "/collections",
    response_model=List[str],
    summary="Get list of available collections in the database",
)
def get_collections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[str]:
    """
    Retrieve the available collection names from the database.

    This endpoint queries the ingestion records table for collection
    names, removes duplicate entries, sorts the results
    alphabetically, and returns the list of available collections.

    Raises:
        HTTPException:
            - 500: If an unexpected error occurs while retrieving the
              collection names.
    """

    try:
        db_records = db.query(IngestionRecord).all()
        db_collections = [r.collection_name for r in db_records if r.collection_name]
    except Exception as exc:
        logger.error(f"Error querying database ingestion records: {exc}")
        db_collections = []

    return sorted(list(set(db_collections)))

