"""Access log model for auditing."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.database import Base


class AccessLog(Base):
    """Access logs table - audit trail for authorization requests."""

    __tablename__ = "access_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
    token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stream_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    protocol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        """String representation of AccessLog."""
        return f"<AccessLog(id={self.id}, result={self.result}, reason={self.reason})>"
