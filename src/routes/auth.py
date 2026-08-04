from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import logger
from src.database.connection import get_db
from src.database.crud import (
    create_user,
    get_user_by_email,
    revoke_token,
)
from src.database.models import User
from src.utils.auth import create_user_token, decode_user_token
from src.utils.deps import get_current_user
from src.utils.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from src.config import JWT_ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(prefix="/auth", tags=["Auth"])
_bearer_scheme = HTTPBearer(auto_error=True)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_TOKEN_EXPIRE_SECONDS: int = JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60


def _hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    return _pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    """Return ``True`` if *plain* matches the bcrypt *hashed* password."""
    return _pwd_context.verify(plain, hashed)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    summary="Register a new user account",
    response_description="The newly created user profile.",
)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    """
    Create a new user account with the given e-mail and password.

    The password is hashed with bcrypt before storage — the plain-text
    password is never persisted.

    Args:
        request: ``RegisterRequest`` containing ``email`` and ``password``.
        db: Active SQLAlchemy database session.

    Returns:
        The newly created :class:`UserResponse` profile.

    Raises:
        HTTPException 409: If the e-mail is already registered.
        HTTPException 500: On unexpected database errors.
    """
    logger.info(f"Registration attempt for email: {request.email}")

    existing = get_user_by_email(db, request.email)
    if existing:
        logger.warning(f"Registration failed – email already registered: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this e-mail address already exists.",
        )

    try:
        hashed = _hash_password(request.password)
        user = create_user(db, email=request.email, hashed_password=hashed)
        logger.info(f"New user registered: id={user.id}, email={user.email}")
        return UserResponse(**user.to_dict())
    except Exception as exc:
        logger.exception(f"Registration failed for {request.email}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again.",
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive a Bearer token",
    response_description="JWT access token valid for 60 minutes.",
)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate a user with their e-mail and password.

    On success, returns a signed JWT that must be passed as
    ``Authorization: Bearer <token>`` on all protected routes.

    Args:
        request: ``LoginRequest`` containing ``email`` and ``password``.
        db: Active SQLAlchemy database session.

    Returns:
        :class:`TokenResponse` with ``access_token``, ``token_type``, and
        ``expires_in`` (seconds).

    Raises:
        HTTPException 401: On invalid credentials or deactivated account.
    """
    logger.info(f"Login attempt for email: {request.email}")

    user = get_user_by_email(db, request.email)
    if not user or not _verify_password(request.password, user.hashed_password):
        logger.warning(f"Login failed – invalid credentials for: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect e-mail or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning(f"Login failed – account deactivated: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, _jti, _expires_at = create_user_token(user_id=user.id, email=user.email)
    logger.info(f"Login successful: id={user.id}, email={user.email}")

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=_TOKEN_EXPIRE_SECONDS,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout and revoke the current Bearer token",
    response_description="Confirmation that the token has been revoked.",
)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Invalidate the current JWT by adding its ``jti`` to the revocation blacklist.

    After calling this endpoint, any subsequent request using the same token
    will receive a **401 Unauthorized** response — even if the token has not
    yet naturally expired.

    Args:
        credentials: Raw HTTPBearer credentials used to extract the token.
        db: Active SQLAlchemy database session.
        current_user: The authenticated user (resolved via ``get_current_user``).

    Returns:
        JSON confirmation message.
    """
    raw_token = credentials.credentials
    payload = decode_user_token(raw_token)
    jti: str = payload["jti"]
    exp: int = payload["exp"]

    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    revoke_token(db, jti=jti, expires_at=expires_at)
    logger.info(f"User logged out: id={current_user.id}, email={current_user.email}, jti={jti}")

    return {"message": "Successfully logged out. Token has been revoked."}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    response_description="The authenticated user's profile.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Return the profile of the currently authenticated user.

    Args:
        current_user: Resolved by the :func:`~src.utils.deps.get_current_user` dependency.

    Returns:
        :class:`UserResponse` with the user's ``id``, ``email``, ``is_active``,
        and timestamps.
    """
    return UserResponse(**current_user.to_dict())
