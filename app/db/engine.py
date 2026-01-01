"""Database engine factory - creates appropriate engine based on database type."""

import logging

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings

logger = logging.getLogger(__name__)


def _get_async_database_url(url: str) -> str:
    """Convert sync database URL to async format.

    Args:
        url: Database URL (sqlite://, postgresql://, mysql://)

    Returns:
        Async-compatible database URL
    """
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    elif url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    elif url.startswith("mysql://"):
        return url.replace("mysql://", "mysql+aiomysql://", 1)
    return url


def _is_sqlite(url: str) -> bool:
    """Check if URL is for SQLite database."""
    return "sqlite" in url.lower()


def create_db_engine(settings: Settings) -> AsyncEngine:
    """Create async database engine based on configuration.

    Args:
        settings: Application settings

    Returns:
        Configured AsyncEngine instance
    """
    async_url = _get_async_database_url(settings.database_url)

    if _is_sqlite(async_url):
        # SQLite - use NullPool to avoid connection conflicts
        engine = create_async_engine(
            async_url,
            echo=settings.log_level == "DEBUG",
            connect_args={"check_same_thread": False, "timeout": 30},
            poolclass=NullPool,
        )
        logger.info("Created SQLite database engine")
    else:
        # PostgreSQL/MySQL - use QueuePool with configured settings
        engine = create_async_engine(
            async_url,
            echo=settings.log_level == "DEBUG",
            pool_pre_ping=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=3600,  # Recycle connections after 1 hour
        )
        logger.info(
            f"Created database engine with pool_size={settings.db_pool_size}, "
            f"max_overflow={settings.db_max_overflow}"
        )

    # Register SQLite-specific event handlers
    if _is_sqlite(settings.database_url):
        _setup_sqlite_pragmas(engine, settings)

    return engine


def _setup_sqlite_pragmas(engine: AsyncEngine, settings: Settings) -> None:
    """Enable foreign key constraints for SQLite connections."""

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        logger.debug("Enabled foreign key constraints for SQLite")
