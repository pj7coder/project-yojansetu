import logging
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger("jansetu.database")
settings = get_settings()

# Configure SQLAlchemy engine with pool pre-ping to detect dropped connections
engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a managed database session.
    Guarantees session rollback on error and proper closure.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error("Database session transaction error: %s", e)
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager yielding a managed database session for background workers and CLI tools.
    Guarantees session rollback on error and proper closure.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error("Database context transaction error: %s", e)
        db.rollback()
        raise
    finally:
        db.close()


def check_database_connection() -> bool:
    """
    Verify PostgreSQL connectivity by executing a lightweight SELECT 1 query.
    Returns True if healthy, False if unreachable without throwing unhandled exceptions.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning("Database connectivity check failed: %s", e)
        return False
