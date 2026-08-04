from __future__ import annotations

import os

import jwt
from sqlalchemy.orm import Session
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import logger
from src.database.models import User
from src.database.connection import get_db
from src.utils.auth import decode_user_token
from src.database.crud import get_user_by_id, is_token_revoked


CRON_SECRET: str | None = os.getenv("CRON_SECRET_KEY")

_bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that validates a user Bearer JWT and returns the active user.

    Performs three checks in order:
    1. Decode and verify the JWT signature and expiry.
    2. Check the token's ``jti`` against the revocation blacklist (logout support).
    3. Load and verify the user from the database (must exist and be active).

    Args:
        credentials: Injected by FastAPI's :class:`HTTPBearer` scheme.
        db: Active SQLAlchemy database session.

    Returns:
        The authenticated :class:`~src.database.models.User` ORM instance.

    Raises:
        HTTPException 401: When the token is missing, expired, revoked, or invalid,
            or when the associated user does not exist or is deactivated.
    """
    raw_token = credentials.credentials

    try:
        payload = decode_user_token(raw_token)
    except jwt.ExpiredSignatureError:
        logger.warning("Bearer token rejected – token has expired.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as exc:
        logger.warning(f"Bearer token rejected – invalid token: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti: str | None = payload.get("jti")
    if not jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token: missing jti claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if is_token_revoked(db, jti):
        logger.warning(f"Bearer token rejected – jti={jti} is revoked (logged out).")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token: missing sub claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token: invalid sub claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(db, user_id)
    if not user:
        logger.warning(f"Bearer token rejected – user_id={user_id} not found in database.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning(f"Bearer token rejected – user_id={user_id} is deactivated.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug(f"Authenticated user: id={user.id}, email={user.email}")
    return user


async def get_current_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> dict:
    """
    Lightweight alias of :func:`get_current_user` that returns the decoded JWT payload.

    Use :func:`get_current_user` when you need the full User ORM object.
    Use this when you only need to confirm the request is authenticated.
    """
    user = await get_current_user(credentials=credentials, db=db)
    return {"sub": str(user.id), "email": user.email}


async def verify_cron_key(x_cron_key: str = Header(...)) -> None:
    """
    FastAPI dependency that validates the ``X-Cron-Key`` header.

    Add to any cron-triggered endpoint to prevent unauthenticated invocations.
    The expected value is read from the ``CRON_SECRET_KEY`` environment variable
    at startup, so it never appears in source code.

    Args:
        x_cron_key: Value of the ``X-Cron-Key`` request header (injected by FastAPI).

    Raises:
        HTTPException 403: When the key is absent, incorrect, or the
            ``CRON_SECRET_KEY`` environment variable is not configured.
    """
    if not CRON_SECRET or x_cron_key != CRON_SECRET:
        logger.warning("Cron key validation failed – invalid or missing X-Cron-Key header.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing cron key.",
        )
