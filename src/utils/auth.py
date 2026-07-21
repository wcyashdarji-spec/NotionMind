from __future__ import annotations

import datetime
from typing import Any, List, Union
import jwt

from src.config import JWT_ALGORITHM, JWT_SECRET_KEY, logger


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
    Verify whether the provided Bearer token has scope to access the specified collection.

    Args:
        token: Bearer token string (or None if missing).
        collection_name: Target collection name to check authorization for.
        secret_key: Secret key for JWT verification.
        algorithm: Hashing algorithm.

    Returns:
        A tuple of `(is_authorized, reason)`.
    """
    if not token or not token.strip():
        return False, "Missing Bearer authorization token."

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
