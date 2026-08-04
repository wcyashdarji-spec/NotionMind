import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN: str | None = os.getenv("NOTION_TOKEN")

LANGSMITH_TRACING: str = os.getenv("LANGSMITH_TRACING")
LANGSMITH_ENDPOINT: str = os.getenv("LANGSMITH_ENDPOINT")
LANGSMITH_API_KEY: str | None = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT")

MILVUS_ENDPOINT: str | None = os.getenv("MILVUS_ENDPOINT")
MILVUS_TOKEN: str | None = os.getenv("MILVUS_TOKEN")
MILVUS_COLLECTION_NAME: str = os.getenv("MILVUS_COLLECTION_NAME", "notion_documentation")

CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "./chroma_db")
CHROMA_COLLECTION_NAME: str = os.getenv("CHROMA_COLLECTION_NAME", "notion_documentation")

EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

DATABASE_URL: str = os.getenv("DATABASE_URL")


DOCS_TOKEN_ENV_MAP: dict[str, str] = {
    # Rivyo
    "rivyo_docs": "Rivyo_Docs",
    "rivyo": "Rivyo_Docs",
    # Editly
    "editly_order_editing_app_docs": "Editly_Order_Editing_App_Docs",
    "editly": "Editly_Order_Editing_App_Docs",
    "editly_order_editing": "Editly_Order_Editing_App_Docs",
    # Wishlist Club
    "wishlist_club_app_docs": "Wishlist_Club_App_Docs",
    "wishlist": "Wishlist_Club_App_Docs",
    "wishlist_club": "Wishlist_Club_App_Docs",
    # Utterbond
    "utterbond_subscription_docs": "Utterbond_Subscription_Docs",
    "utterbond": "Utterbond_Subscription_Docs",
    "utterbond_subscription": "Utterbond_Subscription_Docs",
    # Rebolt
    "rebolt_bundle_docs": "Rebolt_Bundle_Docs",
    "rebolt": "Rebolt_Bundle_Docs",
    "rebolt_bundle": "Rebolt_Bundle_Docs",
    # Addup
    "addup_checkout_docs": "Addup_Checkout_Docs",
    "addup": "Addup_Checkout_Docs",
    "addup_checkout": "Addup_Checkout_Docs",
    # Quickhunt
    "quickhunt_docs": "Quickhunt_Docs",
    "quickhunt": "Quickhunt_Docs",
}


def get_docs_bearer_token(attribute: str) -> str | None:
    """
    Resolve the Bearer token for a given docs attribute name.

    Normalises *attribute* (lowercase, strip, replace spaces/hyphens with
    underscores) and looks it up in :data:`DOCS_TOKEN_ENV_MAP`.  The
    corresponding environment variable is then read at call-time so that
    tokens rotated in the environment are picked up without a restart.

    Args:
        attribute: Human-friendly docs name sent by the client
            (e.g. ``"Rivyo"`` or ``"Editly_Order_Editing_App_Docs"``).

    Returns:
        The raw token string from the environment (may itself be prefixed
        with ``"Bearer "``), or ``None`` if no mapping or env var exists.
    """
    normalised = attribute.strip().lower().replace(" ", "_").replace("-", "_")
    env_key = DOCS_TOKEN_ENV_MAP.get(normalised)
    if not env_key:
        return None
    return os.getenv(env_key)

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE_PATH = LOGS_DIR / "app.log"

_LOG_FORMAT = "[%(asctime)s] %(levelname)s [%(name)s:%(filename)s:%(lineno)d] - %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(name: str = "notion_ingestion") -> logging.Logger:
    """
    Create and configure a named logger with console and file handlers.

    Args:
        name: Logger name (defaults to ``"notion_ingestion"``).

    Returns:
        A configured :class:`logging.Logger` instance.
    """
    log_level_str = os.getenv("LOG_LEVEL", "DEBUG").upper()
    log_level = getattr(logging, log_level_str, logging.DEBUG)

    log = logging.getLogger(name)
    log.setLevel(log_level)

    if log.handlers:
        return log

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    log.addHandler(file_handler)
    log.addHandler(console_handler)
    return log


logger = setup_logger()
