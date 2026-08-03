from fastapi import APIRouter

from src.config import CHROMA_DB_PATH, NOTION_TOKEN, logger

router = APIRouter(prefix="/api", tags=["Health"])


@router.get(
    "/health",
    summary="Service health check",
    response_description="Connection status for Notion and ChromaDB.",
)
async def health_check() -> dict:
    """
    Return the configuration status for both Notion and local ChromaDB.

    Returns:
        JSON object with ``status``, ``notion_configured``, and
        ``chroma_configured`` fields.
    """
    logger.info("Health check requested.")
    notion_ok = bool(NOTION_TOKEN)
    chroma_ok = bool(CHROMA_DB_PATH)

    return {
        "status": "healthy" if notion_ok and chroma_ok else "degraded",
        "notion_configured": notion_ok,
        "chroma_configured": chroma_ok,
        "environment": {
            "chroma_db_path": CHROMA_DB_PATH,
            "has_notion_token": notion_ok,
        },
    }


