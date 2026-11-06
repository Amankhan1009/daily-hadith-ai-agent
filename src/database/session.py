"""
Database Engine and Session Management.

Provides connection configuration, connection pooling, and transactional
session lifecycles for Neon PostgreSQL (and SQLite fallback).
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Union

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config import get_settings


class Base(DeclarativeBase):
    """Declarative base class for all database ORM models."""

    pass


def get_normalized_database_url(raw_url: str) -> Union[str, URL]:
    """
    Ensure PostgreSQL URLs use the modern psycopg v3 driver.
    Returns a SQLAlchemy URL object without masking the password.
    """
    if raw_url.startswith("postgres://") or raw_url.startswith("postgresql://"):
        parsed = make_url(raw_url)
        return parsed.set(drivername="postgresql+psycopg")
    return raw_url


def _get_connect_args(url: str) -> dict[str, Any]:
    """Return dialect-specific connection arguments."""
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {
        "connect_timeout": 15,
    }


settings = get_settings()
db_url = get_normalized_database_url(settings.database_url)

engine = create_engine(
    db_url,
    connect_args=_get_connect_args(settings.database_url),
    echo=settings.log_level == "DEBUG",
    pool_pre_ping=True,  # Vital for Neon serverless sleeping connections
    pool_recycle=300,    # Recycle connections after 5 mins to avoid stale pooler drops
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager yielding a transactional database session.
    Automatically commits on normal exit and rolls back on exception.
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables defined on Base metadata if they do not exist."""
    Base.metadata.create_all(bind=engine)