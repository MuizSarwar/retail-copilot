"""Alembic environment configuration for async SQLAlchemy.

This file configures Alembic to work with the application's async
SQLAlchemy engine and model metadata. It reads the database URL from
the existing application settings (pydantic-settings / .env).
"""

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Ensure the project root is on sys.path so `app` is importable
# regardless of the working directory Alembic runs from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import the application's settings and Base so Alembic can read
# the database URL and discover all model metadata.
from app.core.config import settings
from app.core.database import Base

# Import all model modules so Alembic's autogenerate discovers
# every table defined in the application.
from app.modules.auth.models.role import Role  # noqa: F401
from app.modules.auth.models.user import User  # noqa: F401
from app.modules.products.models.product import Product  # noqa: F401
from app.modules.sales.models.sale import Sale  # noqa: F401
from app.modules.sales.models.sale_item import SaleItem  # noqa: F401

# Alembic Config object, which provides access to values in alembic.ini.
config = context.config

# Override the sqlalchemy.url from alembic.ini with the value from
# the application's settings (.env via pydantic-settings).
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate. Alembic compares this metadata
# against the actual database schema to detect changes.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well.  By skipping the
    Engine creation we don't even need a DBAPI to be available.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given database connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using an async SQLAlchemy engine.

    Alembic itself is synchronous, so we create an async engine,
    obtain a connection, and run migrations inside a synchronous
    thread via `connection.run_sync()`.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a
    connection with the context.  Because the application uses
    async SQLAlchemy, we wrap the async engine execution in
    asyncio.run().
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
