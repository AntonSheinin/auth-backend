"""Active session model for tracking concurrent streams."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.services.database import Base


class ActiveSession(Base):
    """Active sessions table - tracks currently active streaming sessions."""

    __tablename__ = "active_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    token_id: Mapped[int] = mapped_column(Integer, ForeignKey("tokens.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    stream_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    protocol: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_checked_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    def __repr__(self) -> str:
        """String representation of ActiveSession."""
        session_preview = self.session_id[:10] if len(self.session_id) >= 10 else self.session_id
        return (
            f"<ActiveSession(id={self.id}, session_id={session_preview}..., "
            f"user_id={self.user_id}, stream={self.stream_name})>"
        )
