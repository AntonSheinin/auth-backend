"""Main FastAPI application."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.logging import setup_logging
from app.models.database import SessionLocal, init_db
from app.routes import auth_router, management_router
from app.services.session_service import SessionService

# Setup logging first
setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()


async def cleanup_expired_sessions_task() -> None:
    """Background task to periodically clean up expired sessions."""
    while True:
        try:
            await asyncio.sleep(settings.session_cleanup_interval)

            db = SessionLocal()
            try:
                count = SessionService.cleanup_expired_sessions(db)
                if count > 0:
                    logger.info(f"Cleaned up {count} expired sessions")
            except Exception as e:
                logger.error(f"Error during session cleanup: {e}", exc_info=True)
            finally:
                db.close()

        except asyncio.CancelledError:
            logger.info("Session cleanup task cancelled")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in cleanup task: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Flussonic Auth Backend...")
    init_db()
    logger.info(f"Server starting on {settings.api_host}:{settings.api_port}")

    # Start background cleanup task
    cleanup_task = asyncio.create_task(cleanup_expired_sessions_task())
    logger.info("Background cleanup task started")

    yield

    # Shutdown
    logger.info("Shutting down Flussonic Auth Backend...")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("Cleanup task stopped")


# Create FastAPI app
app = FastAPI(
    title="Flussonic Auth Backend",
    description="Authentication backend for Flussonic Media Server with token and session management",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Include routers
app.include_router(auth_router)
app.include_router(management_router)


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": "Flussonic Auth Backend",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health", tags=["health"])
async def health_check() -> JSONResponse:
    """Health check endpoint for Docker."""
    return JSONResponse(
        content={"status": "healthy"},
        status_code=200,
    )


def main() -> None:
    """Entry point for running the application."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
