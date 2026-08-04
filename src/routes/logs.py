from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.config import LOG_FILE_PATH, logger
from src.utils.deps import get_current_token

router = APIRouter(prefix="/api", tags=["Logs"])


@router.get(
    "/logs",
    summary="Tail the application log file",
    response_description="Most recent log lines.",
)
async def get_logs(
    lines: int = Query(default=100, ge=1, le=1000, description="Number of lines to return."),
    _token: dict = Depends(get_current_token),
) -> dict:
    """
    Return the most recent log entries from ``logs/app.log``.

    Args:
        lines: How many tail lines to fetch (1–1000, default 100).

    Returns:
        JSON object with ``log_file``, ``lines_requested``,
        ``lines_returned``, and ``logs`` (list of stripped log strings).

    Raises:
        HTTPException 500: When the log file cannot be read.
    """
    logger.info(f"Log tail requested – last {lines} line(s).")

    if not LOG_FILE_PATH.exists():
        return {
            "log_file": str(LOG_FILE_PATH),
            "lines_requested": lines,
            "lines_returned": 0,
            "logs": [],
            "message": "Log file does not exist yet.",
        }

    try:
        content = LOG_FILE_PATH.read_text(encoding="utf-8").splitlines()
        tail = [ln.strip() for ln in content[-lines:]]
        return {
            "log_file": str(LOG_FILE_PATH),
            "lines_requested": lines,
            "lines_returned": len(tail),
            "logs": tail,
        }

    except Exception as exc:
        logger.error(f"Failed to read log file: {exc}")
        raise HTTPException(status_code=500, detail=f"Could not read log file: {exc}")
