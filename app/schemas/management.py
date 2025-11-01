"""Pydantic schemas for management API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import TokenStatus


class TokenCreate(BaseModel):
    """Schema for creating a new token."""

    token: str = Field(..., min_length=8, max_length=255, description="Token string (must be unique)")
    user_id: str = Field(..., min_length=1, max_length=100, description="User identifier")
    status: TokenStatus = Field(TokenStatus.ACTIVE, description="Token status: active, suspended, expired")
    max_sessions: int = Field(1, ge=1, le=100, description="Maximum concurrent sessions allowed")
    valid_from: datetime | None = Field(None, description="Token valid from (defaults to now)")
    valid_until: datetime | None = Field(None, description="Token valid until (NULL = no expiration)")
    allowed_ips: list[str] | None = Field(None, description="List of allowed IP addresses")
    allowed_streams: list[str] | None = Field(None, description="List of allowed stream names")
    meta: dict[str, Any] | None = Field(None, description="Additional metadata")

    @field_validator("valid_until")
    @classmethod
    def validate_valid_until(cls, v: datetime | None, info: Any) -> datetime | None:
        """Ensure valid_until is after valid_from if both are set."""
        if v is not None and "valid_from" in info.data and info.data["valid_from"] is not None:
            if v <= info.data["valid_from"]:
                raise ValueError("valid_until must be after valid_from")
        return v


class TokenUpdate(BaseModel):
    """Schema for updating an existing token."""

    status: TokenStatus | None = Field(None, description="Token status: active, suspended, expired")
    max_sessions: int | None = Field(None, ge=1, le=100, description="Maximum concurrent sessions allowed")
    valid_until: datetime | None = Field(None, description="Token valid until")
    allowed_ips: list[str] | None = Field(None, description="List of allowed IP addresses")
    allowed_streams: list[str] | None = Field(None, description="List of allowed stream names")
    meta: dict[str, Any] | None = Field(None, description="Additional metadata")


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
    meta: dict[str, Any] | None
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
