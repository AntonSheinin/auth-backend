"""Access log model for auditing"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.models.database import Base


class AccessLog(Base):
    """
    Access logs table - audit trail for authorization requests
    """

    __tablename__ = "access_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=func.now(), index=True)
    token = Column(String(255), nullable=True)
    user_id = Column(String(100), nullable=True)
    stream_name = Column(String(255), nullable=True)
    client_ip = Column(String(45), nullable=True)
    protocol = Column(String(20), nullable=True)
    result = Column(String(20), nullable=False, index=True)  # 'allowed', 'denied'
    reason = Column(String(255), nullable=True)  # denial reason

    def __repr__(self):
        return f"<AccessLog(id={self.id}, result={self.result}, reason={self.reason})>"
