"""Main FastAPI application."""

import asyncio
import logging
import uvicorn
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.exceptions import AuthBackendError, DatabaseError
from app.logging import setup_logging
from app.routes import auth_router, management_router
from app.schemas.auth import ErrorResponse
from app.services.access_log_service import AccessLogService
from app.db import AsyncSessionLocal, init_db
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

            logger.info("Session cleanup task started")
            async with AsyncSessionLocal() as db:
                try:
                    # Cleanup expired sessions
                    session_count = await SessionService.cleanup_expired_sessions(db)
                    logger.info(f"Session cleanup task completed: deleted {session_count} expired session(s)")

                except SQLAlchemyError as e:
                    logger.error(f"Database error during session cleanup: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("Session cleanup task cancelled")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in session cleanup task: {e}", exc_info=True)


async def cleanup_old_logs_task() -> None:
    """Background task to periodically clean up old access logs."""
    while True:
        try:
            await asyncio.sleep(settings.log_cleanup_interval)

            if settings.enable_access_logs:
                logger.info(f"Log cleanup task started (retention: {settings.log_retention_days} days)")
                async with AsyncSessionLocal() as db:
                    try:
                        log_count = await AccessLogService.cleanup_old_logs(db, settings.log_retention_days)
                        logger.info(f"Log cleanup task completed: deleted {log_count} old log(s)")

                    except SQLAlchemyError as e:
                        logger.error(f"Database error during log cleanup: {e}", exc_info=True)
            else:
                logger.debug("Log cleanup task skipped (access logs disabled)")

        except asyncio.CancelledError:
            logger.info("Log cleanup task cancelled")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in log cleanup task: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Flussonic Auth Backend...")
    await init_db()
    logger.info(f"Server starting on {settings.api_host}:{settings.api_port}")

    # Start background cleanup tasks
    session_cleanup_task = asyncio.create_task(cleanup_expired_sessions_task())
    log_cleanup_task = asyncio.create_task(cleanup_old_logs_task())
    logger.info("Background cleanup tasks started")

    yield

    # Shutdown
    logger.info("Shutting down Flussonic Auth Backend...")
    session_cleanup_task.cancel()
    log_cleanup_task.cancel()
    try:
        await session_cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await log_cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("Cleanup tasks stopped")


# Create FastAPI app
app = FastAPI(
    title="Flussonic Auth Backend",
    description="Authentication backend for Flussonic Media Server with token and session management",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================


@app.exception_handler(AuthBackendError)
async def auth_backend_error_handler(request: Request, exc: AuthBackendError) -> JSONResponse:
    """Handle custom application errors.

    Args:
        request: FastAPI request
        exc: Custom exception

    Returns:
        JSON response with error details
    """
    logger.error(
        f"Application error: {exc.message}",
        extra={"error_details": exc.details, "path": request.url.path},
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error=type(exc).__name__,
            message=exc.message,
            details=exc.details,
        ).model_dump(),
    )


@app.exception_handler(DatabaseError)
async def database_error_handler(request: Request, exc: DatabaseError) -> JSONResponse:
    """Handle database errors.

    Args:
        request: FastAPI request
        exc: Database error

    Returns:
        JSON response with error message
    """
    logger.error(
        f"Database error: {exc.message}",
        extra={"error_details": exc.details, "path": request.url.path},
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="DatabaseError",
            message="A database error occurred",
            details=None,  # Don't expose internal details
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors.

    Args:
        request: FastAPI request
        exc: Validation error

    Returns:
        JSON response with validation errors
    """
    logger.warning(
        f"Validation error: {exc}",
        extra={"path": request.url.path, "errors": exc.errors()},
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="ValidationError",
            message="Request validation failed",
            details={"errors": exc.errors()},
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions.

    Args:
        request: FastAPI request
        exc: Unexpected exception

    Returns:
        JSON response with generic error message
    """
    logger.error(
        f"Unexpected error: {exc}",
        extra={"path": request.url.path},
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="InternalServerError",
            message="An unexpected error occurred",
            details=None,
        ).model_dump(),
    )


# Include routers
app.include_router(auth_router)
app.include_router(management_router)


@app.get("/", tags=["info"])
async def root() -> dict[str, str | dict[str, str]]:
    """Root endpoint with API information."""
    return {
        "service": "Flussonic Auth Backend",
        "version": "1.0.0",
        "status": "healthy",
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
            "check": "/check",
            "management": "/api",
        },
    }


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint for Docker."""
    return {"status": "healthy"}


def main() -> None:
    """Entry point for running the application."""
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
