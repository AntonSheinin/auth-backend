"""Database connection and session management."""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class Base(DeclarativeBase):
    """Base class for all database models."""


# Convert database URL to async format
def _get_async_database_url(url: str) -> str:
    """Convert sync database URL to async format."""
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    elif url.startswith("postgresql://") or url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1).replace(
            "postgresql+psycopg://", "postgresql+asyncpg://", 1
        )
    return url


async_database_url = _get_async_database_url(settings.database_url)

# Determine if using SQLite (connection pooling works differently)
is_sqlite = "sqlite" in async_database_url

# Create async SQLAlchemy engine with connection pooling
if is_sqlite:
    # SQLite - use NullPool to avoid connection conflicts
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        async_database_url,
        echo=settings.log_level == "DEBUG",
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=NullPool,
    )
else:
    # PostgreSQL/MySQL - use QueuePool with configured settings
    engine = create_async_engine(
        async_database_url,
        echo=settings.log_level == "DEBUG",
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=3600,  # Recycle connections after 1 hour
    )


# Enable foreign key constraints for SQLite
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign key constraints for SQLite connections."""
    if "sqlite" in settings.database_url:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        logger.debug("Enabled foreign key constraints for SQLite")


# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Async database session dependency for FastAPI."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database - create all tables asynchronously."""
    # Import models to register them with Base
    from app.models.log import AccessLog  # noqa: F401
    from app.models.session import ActiveSession  # noqa: F401
    from app.models.token import Token  # noqa: F401

    logger.info("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully")
