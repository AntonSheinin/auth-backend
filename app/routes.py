"""All API routes consolidated in one file."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.database import get_db
from app.models.token import Token
from app.schemas.auth import DeniedResponse
from app.schemas.management import SessionResponse, TokenCreate, TokenResponse, TokenUpdate
from app.services.session_service import SessionService
from app.services.token_service import TokenService
from app.services.validation import ValidationService

logger = logging.getLogger(__name__)
settings = get_settings()

# Create routers
auth_router = APIRouter(tags=["auth"])
management_router = APIRouter(prefix="/api", tags=["management"])


# ============================================================================
# AUTHORIZATION ENDPOINT (Called by Flussonic)
# ============================================================================


@auth_router.get("/auth")
@auth_router.post("/auth")
async def authorize(
    name: Annotated[str, Query(description="Stream name")],
    ip: Annotated[str, Query(description="Client IP address")],
    token: Annotated[str, Query(description="Authorization token")],
    proto: Annotated[str, Query(description="Protocol (hls, rtmp, rtsp, etc.)")] = "unknown",
    db: Session = Depends(get_db),
) -> Response:
    """
    Main authorization endpoint called by Flussonic Media Server.

    Returns HTTP 200 with headers X-UserId, X-Max-Sessions, X-AuthDuration if authorized.
    Returns HTTP 403 with JSON error details if denied.
    """
    logger.info(f"Auth request: stream={name}, ip={ip}, token={token[:10]}..., proto={proto}")

    # Validate authorization
    is_allowed, denial_reason, token_obj = ValidationService.validate_authorization(
        db=db,
        stream_name=name,
        client_ip=ip,
        token=token,
        protocol=proto,
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
        "token_suspended": "Token has been suspended",
        "token_expired": "Token has expired",
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


# ============================================================================
# MANAGEMENT API - TOKEN ENDPOINTS
# ============================================================================


def verify_api_key(x_api_key: str | None = Header(None)) -> str | None:
    """Verify API key if configured."""
    if settings.api_key and x_api_key != settings.api_key:
        logger.warning(f"Invalid API key attempt: {x_api_key}")
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


@management_router.post("/tokens", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def create_token(
    token_data: TokenCreate,
    db: Session = Depends(get_db),
    _: str | None = Depends(verify_api_key),
) -> TokenResponse:
    """Create a new authentication token."""
    # Check if token already exists
    existing = TokenService.get_by_token(db, token_data.token)
    if existing:
        logger.warning(f"Attempt to create duplicate token: {token_data.token}")
        raise HTTPException(status_code=400, detail="Token already exists")

    db_token = TokenService.create_token(
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

    logger.info(f"Token created: {db_token.token} for user {db_token.user_id}")
    return _token_to_response(db_token)


@management_router.get("/tokens", response_model=list[TokenResponse])
async def list_tokens(
    status_filter: Annotated[str | None, Query(alias="status", description="Filter by status")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    db: Session = Depends(get_db),
    _: str | None = Depends(verify_api_key),
) -> list[TokenResponse]:
    """List all tokens with optional filtering."""
    tokens = TokenService.list_tokens(db, status=status_filter, skip=skip, limit=limit)
    return [_token_to_response(t) for t in tokens]


@management_router.get("/tokens/{token_id}", response_model=TokenResponse)
async def get_token(
    token_id: int,
    db: Session = Depends(get_db),
    _: str | None = Depends(verify_api_key),
) -> TokenResponse:
    """Get a specific token by ID."""
    db_token = TokenService.get_by_id(db, token_id)
    if not db_token:
        raise HTTPException(status_code=404, detail="Token not found")
    return _token_to_response(db_token)


@management_router.patch("/tokens/{token_id}", response_model=TokenResponse)
async def update_token(
    token_id: int,
    token_update: TokenUpdate,
    db: Session = Depends(get_db),
    _: str | None = Depends(verify_api_key),
) -> TokenResponse:
    """Update a token's settings."""
    db_token = TokenService.update_token(
        db=db,
        token_id=token_id,
        status=token_update.status,
        max_sessions=token_update.max_sessions,
        valid_until=token_update.valid_until,
        allowed_ips=token_update.allowed_ips,
        allowed_streams=token_update.allowed_streams,
        meta=token_update.meta,
    )

    if not db_token:
        raise HTTPException(status_code=404, detail="Token not found")

    logger.info(f"Token updated: {db_token.token}")
    return _token_to_response(db_token)


@management_router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_token(
    token_id: int,
    db: Session = Depends(get_db),
    _: str | None = Depends(verify_api_key),
) -> None:
    """Delete a token."""
    success = TokenService.delete_token(db, token_id)
    if not success:
        raise HTTPException(status_code=404, detail="Token not found")
    logger.info(f"Token deleted: ID {token_id}")


# ============================================================================
# MANAGEMENT API - SESSION ENDPOINTS
# ============================================================================


@management_router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    user_id: Annotated[str | None, Query(description="Filter by user ID")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    db: Session = Depends(get_db),
    _: str | None = Depends(verify_api_key),
) -> list:  # noqa: ANN202
    """List active sessions with optional user filtering."""
    sessions = SessionService.list_sessions(db, user_id=user_id, skip=skip, limit=limit)
    return sessions


@management_router.get("/sessions/user/{user_id}", response_model=list[SessionResponse])
async def get_user_sessions(
    user_id: str,
    db: Session = Depends(get_db),
    _: str | None = Depends(verify_api_key),
) -> list:  # noqa: ANN202
    """Get all active sessions for a specific user."""
    sessions = SessionService.get_active_sessions_by_user(db, user_id)
    return sessions


@management_router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def terminate_session(
    session_id: str,
    db: Session = Depends(get_db),
    _: str | None = Depends(verify_api_key),
) -> None:
    """Terminate a specific session."""
    success = SessionService.delete_session(db, session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    logger.info(f"Session terminated: {session_id}")


@management_router.post("/sessions/cleanup", status_code=status.HTTP_200_OK)
async def cleanup_sessions(
    db: Session = Depends(get_db),
    _: str | None = Depends(verify_api_key),
) -> dict[str, int]:
    """Manually trigger cleanup of expired sessions."""
    count = SessionService.cleanup_expired_sessions(db)
    logger.info(f"Cleaned up {count} expired sessions")
    return {"cleaned": count}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _token_to_response(token: Token) -> TokenResponse:
    """Convert Token model to TokenResponse with parsed JSON fields."""
    return TokenResponse(
        id=token.id,
        token=token.token,
        user_id=token.user_id,
        status=token.status,
        max_sessions=token.max_sessions,
        valid_from=token.valid_from,
        valid_until=token.valid_until,
        allowed_ips=token.get_allowed_ips(),
        allowed_streams=token.get_allowed_streams(),
        meta=token.get_meta(),
        created_at=token.created_at,
        updated_at=token.updated_at,
    )
