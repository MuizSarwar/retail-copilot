"""Async database configuration using SQLAlchemy 2.0 and asyncpg.

Components:
- engine: connects to PostgreSQL asynchronously.
- SessionLocal: factory that creates async database sessions.
- Base: declarative base class that all SQLAlchemy models inherit from.
- get_db: FastAPI dependency that yields a session and closes it after the request.
"""

from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import DateTime, func
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
engine = create_async_engine(settings.database_url, echo=False)

# Session factory: creates AsyncSession objects when called.
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session per request.

    Yields a session, then ensures it is closed after the request finishes.
    Use as: db: AsyncSession = Depends(get_db)
    """
    async with SessionLocal() as session:
        yield session