"""Pydantic schemas for auth endpoint"""
from pydantic import BaseModel, Field
from typing import Optional


class AuthRequest(BaseModel):
    """Request from Flussonic for authorization"""

    name: str = Field(..., description="Stream name")
    ip: str = Field(..., description="Client IP address")
    token: str = Field(..., description="Authorization token")
    proto: Optional[str] = Field(None, description="Protocol (hls, rtmp, rtsp, etc.)")


class AuthResponse(BaseModel):
    """Successful authorization response (HTTP 200)"""

    user_id: str = Field(..., description="User identifier for X-UserId header")
    max_sessions: int = Field(..., description="Max concurrent sessions for X-Max-Sessions header")
    auth_duration: int = Field(180, description="Session validity in seconds for X-AuthDuration header")


class DeniedResponse(BaseModel):
    """Access denied response (HTTP 403)"""

    error: str = Field("access_denied", description="Error type")
    reason: str = Field(
        ...,
        description="Denial reason: token_not_found, token_suspended, token_expired, "
        "max_sessions_reached, ip_not_allowed, stream_not_allowed",
    )
    message: str = Field(..., description="Human-readable error message")
    user_id: Optional[str] = Field(None, description="User ID if token was found")
