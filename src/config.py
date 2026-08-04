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

DATABASE_URL: str = os.getenv("DATABASE_URL")

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
