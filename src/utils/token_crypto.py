import base64
from src.config import JWT_SECRET_KEY

def encode_token_str(token: str) -> str:
    """
    Encode a token string using reversible symmetric encoding.

    This function applies an XOR operation between the token and the
    configured secret key, then encodes the result using URL-safe
    Base64. The encoded value can later be restored using
    ``decode_token_str`` and is intended for reversible storage rather
    than cryptographic hashing.

    Args:
        token: Plain-text token to encode.

    Returns:
        str:
            The URL-safe Base64 encoded representation of the token.
    """
    key = JWT_SECRET_KEY or "fallback_default_secret_key"
    key_bytes = key.encode("utf-8")
    token_bytes = token.encode("utf-8")
    encoded_bytes = bytearray(len(token_bytes))
    for i in range(len(token_bytes)):
        encoded_bytes[i] = token_bytes[i] ^ key_bytes[i % len(key_bytes)]
    return base64.urlsafe_b64encode(encoded_bytes).decode("utf-8")


def decode_token_str(encoded_token: str) -> str:
    """
    Decode a previously encoded token string.

    This function reverses the URL-safe Base64 encoding and XOR-based
    transformation applied by ``encode_token_str`` to recover the
    original plain-text token.

    Args:
        encoded_token: Encoded token string to decode.

    Returns:
        str:
            The original plain-text token.

    Raises:
        ValueError:
            If the encoded token cannot be decoded or the decoding
            process fails.
    """
    key = JWT_SECRET_KEY or "fallback_default_secret_key"
    key_bytes = key.encode("utf-8")
    try:
        encoded_bytes = base64.urlsafe_b64decode(encoded_token.encode("utf-8"))
        token_bytes = bytearray(len(encoded_bytes))
        for i in range(len(encoded_bytes)):
            token_bytes[i] = encoded_bytes[i] ^ key_bytes[i % len(key_bytes)]
        return token_bytes.decode("utf-8")
    except Exception as exc:
        raise ValueError(f"Decoding failed: {exc}")
