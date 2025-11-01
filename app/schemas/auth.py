"""Pydantic schemas for auth endpoint."""

from typing import Any

from pydantic import BaseModel, Field, field_validator
import re


class AuthRequest(BaseModel):
    """Request from Flussonic for authorization.

    This schema validates the authorization request that comes from Flussonic Media Server.
    The /auth endpoint is PUBLIC and called by Flussonic - no API key required.

    Success Response (HTTP 200):
        Returns empty body with headers:
        - X-UserId: User identifier
        - X-Max-Sessions: Maximum concurrent sessions allowed
        - X-AuthDuration: Session validity duration in seconds

    Failure Response (HTTP 403):
        Returns JSON with error details (see DeniedResponse schema)
    """

    name: str = Field(..., min_length=1, max_length=255, description="Stream name")
    ip: str = Field(..., description="Client IP address (IPv4 or IPv6)")
    token: str = Field(..., min_length=8, max_length=255, description="Authorization token")
    proto: str = Field(default="unknown", max_length=20, description="Protocol (hls, rtmp, rtsp, etc.)")

    @field_validator("name")
    @classmethod
    def validate_stream_name(cls, v: str) -> str:
        """Validate stream name contains only safe characters."""
        if not re.match(r'^[a-zA-Z0-9_\-./]+$', v):
            raise ValueError("Stream name contains invalid characters")
        return v.strip()

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        """Basic IP address validation."""
        v = v.strip()
        # Simple validation - more detailed validation can be added if needed
        if not re.match(r'^[0-9a-fA-F.:]+$', v):
            raise ValueError("Invalid IP address format")
        return v


class AuthResponse(BaseModel):
    """Successful authorization response (HTTP 200)."""

    user_id: str = Field(..., description="User identifier for X-UserId header")
    max_sessions: int = Field(..., description="Max concurrent sessions for X-Max-Sessions header")
    auth_duration: int = Field(180, description="Session validity in seconds for X-AuthDuration header")


class DeniedResponse(BaseModel):
    """Access denied response (HTTP 403)."""

    error: str = Field("access_denied", description="Error type")
    reason: str = Field(
        ...,
        description="Denial reason: token_not_found, token_suspended, token_expired, "
        "max_sessions_reached, ip_not_allowed, stream_not_allowed",
    )
    message: str = Field(..., description="Human-readable error message")
    user_id: str | None = Field(None, description="User ID if token was found")


class ErrorResponse(BaseModel):
    """Standard error response for API endpoints."""

    error: str = Field(..., description="Error type or code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(None, description="Additional error details")
