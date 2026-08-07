import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.config import logger
from src.database import init_db
from src.routes import agent, auth, health, ingest, logs, search, token


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise database schema on startup; log on shutdown."""
    logger.info("Initializing database schema...")
    init_db()
    logger.info("Notion Ingestion Service is up and ready.")
    yield
    logger.info("Notion Ingestion Service is shutting down.")


app = FastAPI(
    title="Notion → Zilliz Milvus Ingestion Service",
    description=(
        "Recursively crawls hierarchical Notion documentation and indexes "
        "it as hybrid (dense + BM25) vectors in Zilliz Milvus Cloud."
    ),
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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
