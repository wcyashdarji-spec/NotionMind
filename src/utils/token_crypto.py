import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from src.config import JWT_SECRET_KEY, logger

_FALLBACK_KEY = "fallback_default_secret_key"


def _derive_fernet_key(secret: str) -> bytes:
    """
    Derive a Fernet-compatible encryption key from a secret.

    This function uses PBKDF2-HMAC-SHA256 to generate a secure
    32-byte key from the provided secret string. The derived key is
    encoded as a URL-safe Base64 value suitable for initializing a
    Fernet encryption instance.

    Args:
        secret: Secret string used to derive the encryption key.

    Returns:
        bytes:
            A URL-safe Base64 encoded Fernet key.
    """
    raw = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        b"notion_ingestion_token_salt",
        iterations=100_000,
    )
    return base64.urlsafe_b64encode(raw)


def _get_fernet() -> Fernet:
    """
    Create a Fernet encryption instance.

    This function derives an encryption key from the configured
    application secret and returns a ready-to-use Fernet instance for
    encrypting and decrypting token values.

    Returns:
        Fernet:
            Configured Fernet encryption instance.
    """
    key = JWT_SECRET_KEY or _FALLBACK_KEY
    return Fernet(_derive_fernet_key(key))


def _legacy_xor_decode(encoded_token: str) -> str:
    """
    Decode a token created with the legacy XOR encoding scheme.

    This function provides backward compatibility for tokens stored
    before the migration to Fernet encryption. It reverses the
    original XOR-based encoding and returns the recovered plain-text
    token.

    Args:
        encoded_token: Legacy encoded token string.

    Returns:
        str:
            The decoded plain-text token.

    Raises:
        ValueError:
            If the legacy token cannot be decoded.
    """
    key = JWT_SECRET_KEY or _FALLBACK_KEY
    key_bytes = key.encode("utf-8")
    try:
        encoded_bytes = base64.urlsafe_b64decode(encoded_token.encode("utf-8"))
        token_bytes = bytearray(len(encoded_bytes))
        for i in range(len(encoded_bytes)):
            token_bytes[i] = encoded_bytes[i] ^ key_bytes[i % len(key_bytes)]
        return token_bytes.decode("utf-8")
    except Exception as exc:
        raise ValueError(f"Legacy XOR decoding failed: {exc}")


def encode_token_str(token: str) -> str:
    """
    Encrypt a token using Fernet symmetric encryption.

    This function encrypts the supplied token with a Fernet key
    derived from the application's configured secret. The encrypted
    output is URL-safe and suitable for secure database storage.

    Args:
        token: Plain-text token to encrypt.

    Returns:
        str:
            URL-safe encrypted representation of the token.
    """
    f = _get_fernet()
    return f.encrypt(token.encode("utf-8")).decode("utf-8")


def decode_token_str(encoded_token: str) -> str:
    """
    Decrypt an encrypted token string.

    This function first attempts to decrypt the token using Fernet.
    If decryption fails, it falls back to the legacy XOR decoding
    mechanism to maintain compatibility with previously stored
    tokens during migration.

    Args:
        encoded_token: Encrypted token string.

    Returns:
        str:
            The original plain-text token.

    Raises:
        ValueError:
            If the token cannot be decrypted using either the current
            Fernet encryption or the legacy XOR encoding scheme.
    """
    f = _get_fernet()
    try:
        return f.decrypt(encoded_token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        pass

    try:
        plain = _legacy_xor_decode(encoded_token)
        logger.debug(
            "Token decoded using deprecated XOR scheme. "
            "It will be re-encrypted with Fernet on next write."
        )
        return plain
    except ValueError:
        pass

    raise ValueError(
        "Token decoding failed: not a valid Fernet ciphertext "
        "or legacy XOR-encoded token."
    )
