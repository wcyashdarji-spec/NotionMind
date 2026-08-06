import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.config import logger
from src.database import init_db
from src.routes import agent, auth, health, ingest, logs, search, token

app = FastAPI(
    title="Notion → Zilliz Milvus Ingestion Service",
    description=(
        "Recursively crawls hierarchical Notion documentation and indexes "
        "it as hybrid (dense + BM25) vectors in Zilliz Milvus Cloud."
    ),
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(ingest.router)
app.include_router(search.router)
app.include_router(logs.router)
app.include_router(agent.router)
app.include_router(token.router)

os.makedirs("static/images", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", tags=["Root"], summary="Service Information")
async def root() -> dict[str, str]:
    """
    Return basic information about the API service.

    Returns:
        A welcome message along with the service name, version,
        and links to the API documentation.
    """
    return {
        "message": "Welcome to the Notion → Zilliz Milvus Ingestion Service.",
        "version": app.version,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }


@app.on_event("startup")
def on_startup() -> None:
    """Log a startup message and initialize database tables when the ASGI server is ready."""
    logger.info("Initializing database schema...")
    init_db()
    logger.info("Notion Ingestion Service is up and ready.")


@app.on_event("shutdown")
def on_shutdown() -> None:
    """Log a shutdown message when the ASGI server stops."""
    logger.info("Notion Ingestion Service is shutting down.")
