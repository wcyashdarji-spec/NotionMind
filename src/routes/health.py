from fastapi import APIRouter

from src.config import MILVUS_ENDPOINT, MILVUS_TOKEN, NOTION_TOKEN, logger

router = APIRouter(prefix="/api", tags=["Health"])


@router.get(
    "/health",
    summary="Service health check",
    response_description="Connection status for Notion and Milvus.",
)
def health_check() -> dict:
    """
    Return the configuration status for both Notion and Zilliz Milvus.

    Returns:
        JSON object with ``status``, ``notion_configured``, and
        ``milvus_configured`` fields.
    """
    logger.info("Health check requested.")
    notion_ok = bool(NOTION_TOKEN)
    milvus_ok = bool(MILVUS_ENDPOINT and MILVUS_TOKEN)

    return {
        "status": "healthy" if notion_ok and milvus_ok else "degraded",
        "notion_configured": notion_ok,
        "milvus_configured": milvus_ok,
        "environment": {
            "milvus_endpoint": MILVUS_ENDPOINT,
            "has_notion_token": notion_ok,
            "has_milvus_token": milvus_ok,
        },
    }

