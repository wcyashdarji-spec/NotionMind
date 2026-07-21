from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from src.config import DATABASE_URL, logger

Base = declarative_base()


def _get_engine():
    try:
        return create_engine(DATABASE_URL, pool_pre_ping=True)
    except Exception as exc:
        logger.warning(
            f"Failed to initialize database engine for '{DATABASE_URL}': {exc}. "
            "Falling back to local SQLite."
        )
        return create_engine(
            "sqlite:///./notion_ingestion.db",
            connect_args={"check_same_thread": False},
        )


engine = _get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """
    Initialise database tables defined in SQLAlchemy Base metadata.
    """
    global engine, SessionLocal
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
    except Exception as exc:
        logger.warning(
            f"PostgreSQL connection failed during init_db: {exc}. "
            "Falling back to SQLite database for storage."
        )
        fallback_engine = create_engine(
            "sqlite:///./notion_ingestion.db",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=fallback_engine)
        engine = fallback_engine
        SessionLocal.configure(bind=fallback_engine)
        logger.info("Fallback SQLite database initialized successfully.")


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a SQLAlchemy session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
