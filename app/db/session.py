"""Database session management - session factory and FastAPI dependency."""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db.base import Base
from app.db.engine import create_db_engine

logger = logging.getLogger(__name__)

# Create engine and session factory at module level
_settings = get_settings()
engine = create_db_engine(_settings)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Async database session dependency for FastAPI.

    Yields:
        AsyncSession: Database session

    Example:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database - create all tables asynchronously.

    This imports all models to register them with Base.metadata,
    then creates all tables that don't exist.
    """
    # Import models to register them with Base
    from app.models.log import AccessLog  # noqa: F401
    from app.models.session import ActiveSession  # noqa: F401
    from app.models.token import Token  # noqa: F401

    logger.info("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully")
