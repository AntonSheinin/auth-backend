"""Pydantic schemas for management API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TokenCreate(BaseModel):
    """Schema for creating a new token."""

    token: str = Field(..., description="Token string (must be unique)")
    user_id: str = Field(..., description="User identifier")
    status: str = Field("active", description="Token status: active, suspended, expired")
    max_sessions: int = Field(1, description="Maximum concurrent sessions allowed")
    valid_from: datetime | None = Field(None, description="Token valid from (defaults to now)")
    valid_until: datetime | None = Field(None, description="Token valid until (NULL = no expiration)")
    allowed_ips: list[str] | None = Field(None, description="List of allowed IP addresses")
    allowed_streams: list[str] | None = Field(None, description="List of allowed stream names")
    meta: dict | None = Field(None, description="Additional metadata")


class TokenUpdate(BaseModel):
    """Schema for updating an existing token."""

    status: str | None = Field(None, description="Token status: active, suspended, expired")
    max_sessions: int | None = Field(None, description="Maximum concurrent sessions allowed")
    valid_until: datetime | None = Field(None, description="Token valid until")
    allowed_ips: list[str] | None = Field(None, description="List of allowed IP addresses")
    allowed_streams: list[str] | None = Field(None, description="List of allowed stream names")
    meta: dict | None = Field(None, description="Additional metadata")


class TokenResponse(BaseModel):
    """Schema for token response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    token: str
    user_id: str
    status: str
    max_sessions: int
    valid_from: datetime
    valid_until: datetime | None
    allowed_ips: list[str] | None
    allowed_streams: list[str] | None
    meta: dict | None
    created_at: datetime
    updated_at: datetime


class SessionResponse(BaseModel):
    """Schema for active session response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    token_id: int
    user_id: str
    stream_name: str
    client_ip: str
    protocol: str
    started_at: datetime
    last_checked_at: datetime
    expires_at: datetime | None
