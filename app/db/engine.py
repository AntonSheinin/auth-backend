"""Database engine factory - creates PostgreSQL async engine."""

import logging

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import Settings

logger = logging.getLogger(__name__)


def _get_async_database_url(url: str) -> str:
    """Convert sync database URL to async format.

    Args:
        url: Database URL (postgresql://)

    Returns:
        Async-compatible database URL
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    return url


def create_db_engine(settings: Settings) -> AsyncEngine:
    """Create async PostgreSQL database engine.

    Args:
        settings: Application settings

    Returns:
        Configured AsyncEngine instance
    """
    async_url = _get_async_database_url(settings.database_url)

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

    return engine
