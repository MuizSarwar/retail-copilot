"""Async database configuration using SQLAlchemy 2.0 and asyncpg.

Components:
- engine: connects to PostgreSQL asynchronously.
- SessionLocal: factory that creates async database sessions.
- Base: declarative base class that all SQLAlchemy models inherit from.
- get_db: FastAPI dependency that yields a session and closes it after the request.
"""

from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import DateTime, func, pool
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, mapped_column

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base. All SQLAlchemy models inherit from this class."""

    pass


# Reusable column definitions for timestamps.
# These are used directly in model classes to avoid mixin issues.


def created_at_column() -> mapped_column:
    """Return a created_at column with server default timestamp."""
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def updated_at_column() -> mapped_column:
    """Return an updated_at column with server default and onupdate timestamp."""
    return mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# Create the async engine. asyncpg is the driver that talks to PostgreSQL.
# NullPool creates a fresh connection for each operation, avoiding
# connection pool corruption on Windows with asyncpg.
database_url = settings.database_url
if settings.app_env == "testing":
    # Safety check: never use the development database for tests.
    if settings.test_database_url == settings.database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL must not equal DATABASE_URL. "
            "Tests must use a separate database to avoid destroying dev data."
        )
    database_url = settings.test_database_url

engine = create_async_engine(database_url, echo=False, poolclass=pool.NullPool)

# Session factory: creates AsyncSession objects when called.
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session per request.

    Yields a session, commits on success, rolls back on error, and ensures
    the session is closed after the request finishes.
    Use as: db: AsyncSession = Depends(get_db)
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise