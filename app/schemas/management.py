"""Pydantic schemas for management API"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TokenCreate(BaseModel):
    """Schema for creating a new token"""

    token: str = Field(..., description="Token string (must be unique)")
    user_id: str = Field(..., description="User identifier")
    status: str = Field("active", description="Token status: active, suspended, expired")
    max_sessions: int = Field(1, description="Maximum concurrent sessions allowed")
    valid_from: Optional[datetime] = Field(None, description="Token valid from (defaults to now)")
    valid_until: Optional[datetime] = Field(None, description="Token valid until (NULL = no expiration)")
    allowed_ips: Optional[List[str]] = Field(None, description="List of allowed IP addresses")
    allowed_streams: Optional[List[str]] = Field(None, description="List of allowed stream names")
    metadata: Optional[dict] = Field(None, description="Additional metadata")


class TokenUpdate(BaseModel):
    """Schema for updating an existing token"""

    status: Optional[str] = Field(None, description="Token status: active, suspended, expired")
    max_sessions: Optional[int] = Field(None, description="Maximum concurrent sessions allowed")
    valid_until: Optional[datetime] = Field(None, description="Token valid until")
    allowed_ips: Optional[List[str]] = Field(None, description="List of allowed IP addresses")
    allowed_streams: Optional[List[str]] = Field(None, description="List of allowed stream names")
    metadata: Optional[dict] = Field(None, description="Additional metadata")


class TokenResponse(BaseModel):
    """Schema for token response"""

    id: int
    token: str
    user_id: str
    status: str
    max_sessions: int
    valid_from: datetime
    valid_until: Optional[datetime]
    allowed_ips: Optional[List[str]]
    allowed_streams: Optional[List[str]]
    metadata: Optional[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SessionResponse(BaseModel):
    """Schema for active session response"""

    id: int
    session_id: str
    token_id: int
    user_id: str
    stream_name: str
    client_ip: str
    protocol: str
    started_at: datetime
    last_checked_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True
