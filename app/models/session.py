"""Active session model for tracking concurrent streams"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.models.database import Base


class ActiveSession(Base):
    """
    Active sessions table - tracks currently active streaming sessions
    """

    __tablename__ = "active_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)  # hash(name+ip+token)
    token_id = Column(Integer, ForeignKey("tokens.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(100), nullable=False, index=True)
    stream_name = Column(String(255), nullable=False)
    client_ip = Column(String(45), nullable=False)
    protocol = Column(String(20), nullable=False)
    started_at = Column(DateTime, default=func.now())
    last_checked_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=True, index=True)  # Based on X-AuthDuration

    def __repr__(self):
        return (
            f"<ActiveSession(id={self.id}, session_id={self.session_id[:10]}..., "
            f"user_id={self.user_id}, stream={self.stream_name})>"
        )
