"""Token model for authentication."""

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.services.database import Base

logger = logging.getLogger(__name__)


class Token(Base):
    """Token table - stores authentication tokens with their configuration."""

    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    max_sessions: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    allowed_ips: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_streams: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    def get_allowed_ips(self) -> list[str] | None:
        """Parse allowed_ips JSON field."""
        if not self.allowed_ips:
            return None
        try:
            return json.loads(self.allowed_ips)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse allowed_ips for token {self.id}: {e}")
            return None

    def get_allowed_streams(self) -> list[str] | None:
        """Parse allowed_streams JSON field."""
        if not self.allowed_streams:
            return None
        try:
            return json.loads(self.allowed_streams)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse allowed_streams for token {self.id}: {e}")
            return None

    def get_meta(self) -> dict[str, Any]:
        """Parse metadata JSON field."""
        if not self.meta:
            return {}
        try:
            return json.loads(self.meta)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse meta for token {self.id}: {e}")
            return {}

    def set_allowed_ips(self, ips: list[str]) -> None:
        """Set allowed_ips as JSON."""
        self.allowed_ips = json.dumps(ips)

    def set_allowed_streams(self, streams: list[str]) -> None:
        """Set allowed_streams as JSON."""
        self.allowed_streams = json.dumps(streams)

    def set_meta(self, data: dict[str, Any]) -> None:
        """Set metadata as JSON."""
        self.meta = json.dumps(data)

    def __repr__(self) -> str:
        """String representation of Token."""
        token_preview = self.token[:10] if len(self.token) >= 10 else self.token
        return f"<Token(id={self.id}, token={token_preview}..., user_id={self.user_id}, status={self.status})>"
