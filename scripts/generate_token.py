"""
Token Generator Script for Notion Ingestion MCP Server.

Generates a signed JWT Bearer token with scope for specific collections
(e.g., 'Rivyo_docs' or 'Editly_Order_Editing_App').

Usage:
    python scripts/generate_token.py --collection Rivyo_docs
    python scripts/generate_token.py --collection Editly_Order_Editing_App --expires-days 60
    python scripts/generate_token.py --collection Rivyo_docs Editly_Order_Editing_App
"""

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.resolve()))

from src.config import JWT_ALGORITHM, JWT_SECRET_KEY
from src.utils.auth import decode_token, generate_access_token


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a JWT Bearer token for MCP collection authorization."
    )
    parser.add_argument(
        "--collection",
        "-c",
        nargs="+",
        required=True,
        help="One or more collection names (e.g., 'Rivyo_docs', 'Editly_Order_Editing_App').",
    )
    parser.add_argument(
        "--expires-days",
        "-d",
        type=int,
        default=30,
        help="Expiration period in days (default: 30).",
    )
    parser.add_argument(
        "--secret",
        type=str,
        default=JWT_SECRET_KEY,
        help="Optional JWT secret key override.",
    )

    args = parser.parse_args()

    collections = args.collection
    if len(collections) == 1 and "," in collections[0]:
        collections = [c.strip() for c in collections[0].split(",") if c.strip()]

    token = generate_access_token(
        collections=collections,
        expires_days=args.expires_days,
        secret_key=args.secret,
        algorithm=JWT_ALGORITHM,
    )

    decoded = decode_token(token, secret_key=args.secret, algorithm=JWT_ALGORITHM)

    print("\n" + "=" * 65)
    print("      JWT BEARER TOKEN GENERATOR FOR NOTION MCP SERVER")
    print("=" * 65)
    print(f"Target Collection(s) : {collections}")
    print(f"Expires In           : {args.expires_days} days")
    print(f"Token Issued At      : {decoded.get('iat')}")
    print(f"Token Expiration     : {decoded.get('exp')}")
    print("-" * 65)
    print("Generated Bearer Token:")
    print(token)
    print("-" * 65)
    print("Usage Example in Authorization Header:")
    print(f"Authorization: Bearer {token}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
