from __future__ import annotations

import datetime
import uuid
from typing import Any, List, Union
import jwt

from src.database.models import GeneratedToken
from src.database.connection import SessionLocal
from src.utils.token_crypto import decode_token_str
from src.config import JWT_ALGORITHM, JWT_ACCESS_TOKEN_EXPIRE_MINUTES, JWT_SECRET_KEY, logger

_USER_TOKEN_EXPIRE_MINUTES: int = JWT_ACCESS_TOKEN_EXPIRE_MINUTES


def generate_access_token(
    collections: Union[List[str], str],
    expires_days: int = 30,
    secret_key: str = JWT_SECRET_KEY,
    algorithm: str = JWT_ALGORITHM,
) -> str:
    """
    Generate a signed JWT Bearer token with scope restricted to target collections.

    Args:
        collections: Single collection name string or list of allowed collection names.
            Example: "Rivyo_docs" or ["Rivyo_docs", "Editly_Order_Editing_App"].
        expires_days: Expiration period in days (default 30).
        secret_key: Secret key used to sign the token.
        algorithm: Hashing algorithm (default HS256).

    Returns:
        Encoded JWT token string.
    """
    try:
        if isinstance(collections, str):
            collection_list = [collections]
        else:
            collection_list = list(collections)

        now = datetime.datetime.now(datetime.timezone.utc)
        expiration = now + datetime.timedelta(days=expires_days)

        payload = {
            "collections": collection_list,
            "scope": " ".join(collection_list),
            "iat": int(now.timestamp()),
            "exp": int(expiration.timestamp()),
        }

        token = jwt.encode(payload, secret_key, algorithm=algorithm)
        logger.info(f"Generated JWT token for collection scope: {collection_list}")
        return token
    
    except Exception as exc:
        logger.error(f"Error generating JWT token: {exc}")
        raise

def decode_token(
    token: str,
    secret_key: str = JWT_SECRET_KEY,
    algorithm: str = JWT_ALGORITHM,
) -> dict[str, Any]:
    """
    Decode and verify a JWT Bearer token.

    Args:
        token: Raw or 'Bearer '-prefixed JWT string.
        secret_key: Secret key for signature verification.
        algorithm: Hashing algorithm.

    Returns:
        Decoded payload dictionary.

    Raises:
        jwt.ExpiredSignatureError: If token has expired.
        jwt.InvalidTokenError: If token signature or structure is invalid.
    """
    token_str = token.strip()
    if token_str.lower().startswith("bearer "):
        token_str = token_str[7:].strip()

    return jwt.decode(token_str, secret_key, algorithms=[algorithm])


def verify_collection_access(
    token: str | None,
    collection_name: str,
    secret_key: str = JWT_SECRET_KEY,
    algorithm: str = JWT_ALGORITHM,
) -> tuple[bool, str]:
    """
    Verify that a bearer token is authorized to access a collection.

    This function validates the provided token against the database,
    ensuring it exists, is active, has not expired, and is authorized
    for the requested collection. It then verifies the JWT signature
    and extracts the token's collection scope before determining
    whether access should be granted.

    Args:
        token: Bearer token supplied by the client.
        collection_name: Name of the collection being accessed.
        secret_key: Secret key used to verify the JWT signature.
        algorithm: JWT signing algorithm.

    Returns:
        tuple[bool, str]:
            A tuple containing:
            - A boolean indicating whether access is authorized.
            - A descriptive message explaining the authorization result
              or the reason for failure.
    """
    if not token or not token.strip():
        return False, "Missing Bearer authorization token."

    token_str = token.strip()
    if token_str.lower().startswith("bearer "):
        token_str = token_str[7:].strip()

    db = SessionLocal()
    try:
        tokens = (
            db.query(GeneratedToken)
            .filter(GeneratedToken.collection_name.in_([collection_name, "*"]))
            .all()
        )
        db_token = None
        for t in tokens:
            try:
                if decode_token_str(t.token) == token_str:
                    db_token = t
                    break
            except Exception:
                continue

        if not db_token:
            logger.warning("Token verification failed: Token not found in database.")
            return False, "Authorization token not registered in database."
        if not db_token.is_valid:
            logger.warning(f"Token verification failed: Token ID={db_token.id} has been invalidated.")
            return False, "Authorization token has been invalidated (replaced by a newer one or revoked)."
        
        now = datetime.datetime.now(datetime.timezone.utc)

        expires_at = db_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
        if expires_at < now:
            logger.warning(f"Token verification failed: Token ID={db_token.id} has expired.")
            return False, "Authorization token has expired."
            
        if db_token.collection_name != "*" and db_token.collection_name != collection_name:
            logger.warning(f"Token verification failed: Token ID={db_token.id} is for '{db_token.collection_name}', not requested '{collection_name}'.")
            return False, f"Authorization token is not valid for collection '{collection_name}'."
            
    except Exception as exc:
        logger.error(f"Database error during token verification: {exc}")
        return False, f"Token validation failed due to database error: {exc}"
    finally:
        db.close()

    try:
        payload = decode_token(token, secret_key=secret_key, algorithm=algorithm)
    except jwt.ExpiredSignatureError:
        return False, "Authorization token has expired."
    except jwt.InvalidTokenError as exc:
        return False, f"Invalid authorization token: {exc}"
    except Exception as exc:
        return False, f"Token validation failed: {exc}"

    allowed_collections: list[str] = []
    if "collections" in payload:
        cols = payload["collections"]
        if isinstance(cols, list):
            allowed_collections.extend(cols)
        elif isinstance(cols, str):
            allowed_collections.append(cols)

    if "scope" in payload and isinstance(payload["scope"], str):
        for item in payload["scope"].split():
            if item not in allowed_collections:
                allowed_collections.append(item)

    if "*" in allowed_collections or collection_name in allowed_collections:
        return True, f"Access granted to collection '{collection_name}'."

    return (
        False,
        f"Access denied: Token scope does not grant access to collection '{collection_name}'. "
        f"Token collections: {allowed_collections}",
    )


def create_user_token(
    user_id: int,
    email: str,
    expires_minutes: int = _USER_TOKEN_EXPIRE_MINUTES,
    secret_key: str = JWT_SECRET_KEY,
    algorithm: str = JWT_ALGORITHM,
) -> tuple[str, str, datetime.datetime]:
    """
    Generate a signed JWT for an authenticated user session.

    The token payload includes:
    - ``sub``  – user ID (as string) for :func:`get_user_by_id` lookup
    - ``email``– user e-mail address
    - ``jti``  – unique token identifier (UUID4) used for logout blacklisting
    - ``iat``  – issued-at timestamp
    - ``exp``  – expiry timestamp

    Args:
        user_id: Database primary key of the authenticated user.
        email: User's e-mail address (informational claim).
        expires_minutes: Token lifetime in minutes (default 60).
        secret_key: JWT signing secret.
        algorithm: Signing algorithm.

    Returns:
        A 3-tuple of ``(encoded_token, jti, expires_at_datetime)``.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(minutes=expires_minutes)
    jti = str(uuid.uuid4())

    payload = {
        "sub": str(user_id),
        "email": email,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    token = jwt.encode(payload, secret_key, algorithm=algorithm)
    logger.info(f"User session token created – user_id={user_id}, jti={jti}")
    return token, jti, expires_at


def decode_user_token(
    token: str,
    secret_key: str = JWT_SECRET_KEY,
    algorithm: str = JWT_ALGORITHM,
) -> dict[str, Any]:
    """
    Decode and verify a user session JWT.

    Strips an optional ``Bearer `` prefix before decoding.

    Args:
        token: Raw or ``"Bearer "``-prefixed JWT string.
        secret_key: Secret key for signature verification.
        algorithm: Signing algorithm.

    Returns:
        Decoded payload dictionary (contains ``sub``, ``email``, ``jti``, ``exp``).

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If the token is malformed or the signature is invalid.
    """
    token_str = token.strip()
    if token_str.lower().startswith("bearer "):
        token_str = token_str[7:].strip()
    return jwt.decode(token_str, secret_key, algorithms=[algorithm])
