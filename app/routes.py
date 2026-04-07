"""All API routes consolidated in one file."""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.enums import AccessResult, TokenStatus
from app.exceptions import DatabaseError, SessionNotFoundError, TokenAlreadyExistsError, TokenNotFoundError
from app.mappers import TokenMapper
from app.schemas.auth import DeniedResponse
from app.schemas.management import AccessLogResponse, SessionResponse, TokenCreate, TokenResponse, TokenUpdate
from app.db import get_db
from app.services.access_log_service import AccessLogService
from app.services.session_service import SessionService
from app.services.token_service import TokenService
from app.services.validation import ValidationService

logger = logging.getLogger(__name__)

# Create routers
auth_router = APIRouter(tags=["auth"])
management_router = APIRouter(prefix="/api", tags=["management"])


# ============================================================================
# DEPENDENCIES
# ============================================================================


def get_settings_dependency() -> Settings:
    """Dependency to inject settings."""
    return get_settings()


def verify_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings_dependency),
) -> None:
    """Verify API key if configured.

    Args:
        x_api_key: API key from request header
        settings: Application settings

    Raises:
        HTTPException: If API key is required but missing or invalid
    """
    if settings.api_key and x_api_key != settings.api_key:
        logger.warning("Invalid API key attempt detected")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


# ============================================================================
# AUTHORIZATION ENDPOINT (Called by Flussonic)
# ============================================================================


@auth_router.get("/auth")
@auth_router.post("/auth")
async def authorize(
    name: Annotated[str, Query(description="Stream name", min_length=1, max_length=255)],
    ip: Annotated[str, Query(description="Client IP address", min_length=1, max_length=45)],
    token: Annotated[str | None, Query(description="Authorization token", max_length=255)] = None,
    proto: Annotated[str, Query(description="Protocol (hls, rtmp, rtsp, etc.)", max_length=20)] = "unknown",
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
) -> Response:
    """Main authorization endpoint called by Flussonic Media Server.

    This endpoint is PUBLIC and does not require API key authentication.
    It is called by Flussonic for every stream access request.

    Success Response (HTTP 200):
        Empty body with headers:
        - X-UserId: User identifier
        - X-Max-Sessions: Maximum concurrent sessions allowed
        - X-AuthDuration: Session validity duration in seconds

    Failure Response (HTTP 403):
        JSON body with error details (see DeniedResponse schema)

    Args:
        name: Stream name being accessed
        ip: Client IP address
        token: Authorization token
        proto: Protocol used (default: "unknown")
        db: Database session
        settings: Application settings

    Returns:
        HTTP 200 with headers if authorized, HTTP 403 with JSON if denied

    Raises:
        HTTPException: On internal errors (500)
    """
    if not token or not token.strip():
        logger.warning(f"Access DENIED: reason=missing_token, stream={name}, ip={ip}")
        error_response = DeniedResponse(
            error="access_denied",
            reason="missing_token",
            message="Missing token query parameter",
            user_id=None,
        )
        return Response(
            content=error_response.model_dump_json(),
            status_code=status.HTTP_403_FORBIDDEN,
            media_type="application/json",
        )

    token = token.strip()
    # Mask token in logs for security
    token_preview = token[:8] + "..." if len(token) > 8 else token
    logger.info(f"Auth request: stream={name}, ip={ip}, token={token_preview}, proto={proto}")

    try:
        # Validate authorization
        is_allowed, denial_reason, token_obj = await ValidationService.validate_authorization(
            db=db,
            stream_name=name,
            client_ip=ip,
            token=token,
            protocol=proto,
            settings=settings,
        )

        if is_allowed and token_obj:
            # Access granted - return 200 with headers
            logger.info(f"Access GRANTED: user_id={token_obj.user_id}, stream={name}")

            response = Response(status_code=status.HTTP_200_OK)
            response.headers["X-UserId"] = token_obj.user_id
            response.headers["X-Max-Sessions"] = str(token_obj.max_sessions)
            response.headers["X-AuthDuration"] = str(settings.auth_duration)

            return response

        # Access denied - return 403 with JSON error
        logger.warning(f"Access DENIED: reason={denial_reason}, stream={name}, ip={ip}")

        error_messages = {
            "token_not_found": "Invalid or unknown token",
            "missing_token": "Missing token query parameter",
            "token_suspended": "Token has been suspended",
            "token_expired": "Token has expired",
            "token_invalid_status": "Token has an invalid status",
            "token_not_yet_valid": "Token is not yet valid",
            "max_sessions_reached": f"Maximum concurrent sessions limit reached ({token_obj.max_sessions if token_obj else 'N/A'})",
            "ip_not_allowed": f"IP address {ip} is not authorized for this token",
            "stream_not_allowed": f"Stream '{name}' is not authorized for this token",
        }

        error_response = DeniedResponse(
            error="access_denied",
            reason=denial_reason or "unknown",
            message=error_messages.get(denial_reason or "", "Access denied"),
            user_id=token_obj.user_id if token_obj else None,
        )

        return Response(
            content=error_response.model_dump_json(),
            status_code=status.HTTP_403_FORBIDDEN,
            media_type="application/json",
        )

    except DatabaseError as e:
        logger.error(f"Database error during authorization: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authorization",
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error during authorization: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


# ============================================================================
# MANAGEMENT API - TOKEN ENDPOINTS
# ============================================================================


@management_router.post("/tokens", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def create_token(
    token_data: TokenCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
) -> TokenResponse:
    """Create a new authentication token.

    Args:
        token_data: Token creation data
        db: Database session
        _: API key verification

    Returns:
        Created token

    Raises:
        HTTPException: If token already exists (400) or database error (500)
    """
    try:
        # Check if token already exists
        existing = await TokenService.get_by_token(db, token_data.token)
        if existing:
            logger.warning(f"Attempt to create duplicate token: {token_data.token[:10]}...")
            raise TokenAlreadyExistsError(token_data.token)

        db_token = await TokenService.create_token(
            db=db,
            token=token_data.token,
            user_id=token_data.user_id,
            status=token_data.status,
            max_sessions=token_data.max_sessions,
            valid_from=token_data.valid_from,
            valid_until=token_data.valid_until,
            allowed_ips=token_data.allowed_ips,
            allowed_streams=token_data.allowed_streams,
            meta=token_data.meta,
        )

        await db.commit()
        logger.info(f"Token created: {db_token.token[:10]}... for user {db_token.user_id}")
        return TokenMapper.to_response(db_token)

    except TokenAlreadyExistsError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message) from e
    except DatabaseError as e:
        await db.rollback()
        logger.error(f"Database error creating token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create token",
        ) from e


@management_router.get("/tokens", response_model=list[TokenResponse])
async def list_tokens(
    status_filter: Annotated[TokenStatus | None, Query(alias="status", description="Filter by status")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
) -> list[TokenResponse]:
    """List all tokens with optional filtering.

    Args:
        status_filter: Optional status filter
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        _: API key verification

    Returns:
        List of tokens

    Raises:
        HTTPException: On database error (500)
    """
    try:
        tokens = await TokenService.list_tokens(db, status=status_filter, skip=skip, limit=limit)
        return TokenMapper.to_response_list(tokens)
    except DatabaseError as e:
        logger.error(f"Database error listing tokens: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tokens",
        ) from e


@management_router.get("/tokens/{token_id}", response_model=TokenResponse)
async def get_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
) -> TokenResponse:
    """Get a specific token by ID.

    Args:
        token_id: Token ID
        db: Database session
        _: API key verification

    Returns:
        Token details

    Raises:
        HTTPException: If token not found (404) or database error (500)
    """
    try:
        db_token = await TokenService.get_by_id(db, token_id)
        if not db_token:
            raise TokenNotFoundError(str(token_id))
        return TokenMapper.to_response(db_token)
    except TokenNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from e
    except DatabaseError as e:
        logger.error(f"Database error getting token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get token",
        ) from e


@management_router.patch("/tokens/{token_id}", response_model=TokenResponse)
async def update_token(
    token_id: int,
    token_update: TokenUpdate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
) -> TokenResponse:
    """Update a token's settings.

    Args:
        token_id: Token ID to update
        token_update: Updated token data
        db: Database session
        _: API key verification

    Returns:
        Updated token

    Raises:
        HTTPException: If token not found (404) or database error (500)
    """
    try:
        db_token = await TokenService.update_token(
            db=db,
            token_id=token_id,
            status=token_update.status,
            max_sessions=token_update.max_sessions,
            valid_until=token_update.valid_until,
            allowed_ips=token_update.allowed_ips,
            allowed_streams=token_update.allowed_streams,
            meta=token_update.meta,
        )

        await db.commit()
        logger.info(f"Token updated: {db_token.token[:10]}...")
        return TokenMapper.to_response(db_token)

    except TokenNotFoundError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from e
    except DatabaseError as e:
        await db.rollback()
        logger.error(f"Database error updating token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update token",
        ) from e


@management_router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
) -> None:
    """Delete a token.

    Note: Due to CASCADE DELETE, all active sessions associated with this token
    will also be deleted automatically.

    Args:
        token_id: Token ID to delete
        db: Database session
        _: API key verification

    Raises:
        HTTPException: If token not found (404) or database error (500)
    """
    try:
        await TokenService.delete_token(db, token_id)
        await db.commit()
        logger.info(f"Token deleted: ID {token_id}")
    except TokenNotFoundError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from e
    except DatabaseError as e:
        await db.rollback()
        logger.error(f"Database error deleting token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete token",
        ) from e


# ============================================================================
# MANAGEMENT API - SESSION ENDPOINTS
# ============================================================================


@management_router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    user_id: Annotated[str | None, Query(description="Filter by user ID")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
) -> list[SessionResponse]:
    """List active sessions with optional user filtering.

    Args:
        user_id: Optional user ID filter
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        _: API key verification

    Returns:
        List of active sessions

    Raises:
        HTTPException: On database error (500)
    """
    try:
        sessions = await SessionService.list_sessions(db, user_id=user_id, skip=skip, limit=limit)
        # Convert ORM models to Pydantic schemas
        return [SessionResponse.model_validate(session) for session in sessions]
    except DatabaseError as e:
        logger.error(f"Database error listing sessions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list sessions",
        ) from e


@management_router.get("/sessions/user/{user_id}", response_model=list[SessionResponse])
async def get_user_sessions(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
) -> list[SessionResponse]:
    """Get all active sessions for a specific user.

    Args:
        user_id: User identifier
        db: Database session
        _: API key verification

    Returns:
        List of active sessions for the user

    Raises:
        HTTPException: On database error (500)
    """
    try:
        sessions = await SessionService.get_active_sessions_by_user(db, user_id)
        # Convert ORM models to Pydantic schemas
        return [SessionResponse.model_validate(session) for session in sessions]
    except DatabaseError as e:
        logger.error(f"Database error getting user sessions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user sessions",
        ) from e


@management_router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def terminate_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
) -> None:
    """Terminate a specific session.

    Args:
        session_id: Session ID to terminate
        db: Database session
        _: API key verification

    Raises:
        HTTPException: If session not found (404) or database error (500)
    """
    try:
        await SessionService.delete_session(db, session_id)
        await db.commit()
        logger.info(f"Session terminated: {session_id[:10]}...")
    except SessionNotFoundError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from e
    except DatabaseError as e:
        await db.rollback()
        logger.error(f"Database error terminating session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to terminate session",
        ) from e


@management_router.post("/sessions/cleanup", status_code=status.HTTP_200_OK)
async def cleanup_sessions(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
) -> dict[str, int]:
    """Manually trigger cleanup of expired sessions.

    This endpoint is useful for testing or manual cleanup.
    Normally, expired sessions are cleaned up automatically by a background task.

    Args:
        db: Database session
        _: API key verification

    Returns:
        Dictionary with count of cleaned sessions

    Raises:
        HTTPException: On database error (500)
    """
    try:
        count = await SessionService.cleanup_expired_sessions(db)
        logger.info(f"Cleaned up {count} expired sessions")
        return {"cleaned": count}
    except DatabaseError as e:
        logger.error(f"Database error during cleanup: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup sessions",
        ) from e


# ============================================================================
# MANAGEMENT API - ACCESS LOGS
# ============================================================================


@management_router.get("/access-logs", response_model=list[AccessLogResponse])
async def list_access_logs(
    user_id: Annotated[str | None, Query(description="Filter by user ID")] = None,
    token: Annotated[str | None, Query(description="Filter by token")] = None,
    stream_name: Annotated[str | None, Query(description="Filter by stream name")] = None,
    client_ip: Annotated[str | None, Query(description="Filter by client IP")] = None,
    protocol: Annotated[str | None, Query(description="Filter by protocol")] = None,
    result: Annotated[AccessResult | None, Query(description="Filter by access result")] = None,
    reason: Annotated[str | None, Query(description="Filter by result reason")] = None,
    start_time: Annotated[datetime | None, Query(description="Filter logs from this timestamp (inclusive)")] = None,
    end_time: Annotated[datetime | None, Query(description="Filter logs until this timestamp (inclusive)")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
) -> list[AccessLogResponse]:
    """List access logs with optional filtering.

    Args:
        user_id: Optional user ID filter
        token: Optional token filter
        stream_name: Optional stream name filter
        client_ip: Optional client IP filter
        protocol: Optional protocol filter
        result: Optional access result filter
        reason: Optional denial reason filter
        start_time: Optional start timestamp (inclusive)
        end_time: Optional end timestamp (inclusive)
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        _: API key verification

    Returns:
        List of access log entries

    Raises:
        HTTPException: On invalid time range (400) or database error (500)
    """
    if start_time and end_time and start_time > end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must be before end_time",
        )

    try:
        logs = await AccessLogService.list_access_logs(
            db=db,
            user_id=user_id,
            token=token,
            stream_name=stream_name,
            client_ip=client_ip,
            protocol=protocol,
            result=result,
            reason=reason,
            start_time=start_time,
            end_time=end_time,
            skip=skip,
            limit=limit,
        )
        return [AccessLogResponse.model_validate(log) for log in logs]
    except DatabaseError as e:
        logger.error(f"Database error listing access logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list access logs",
        ) from e
