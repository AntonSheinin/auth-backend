"""Session service for managing active streaming sessions."""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.session import ActiveSession


class SessionService:
    """Service for session-related database operations"""

    @staticmethod
    def get_by_session_id(db: Session, session_id: str) -> ActiveSession | None:
        """Get session by session ID."""
        return db.query(ActiveSession).filter(ActiveSession.session_id == session_id).first()

    @staticmethod
    def get_active_sessions_by_user(db: Session, user_id: str) -> list[ActiveSession]:
        """Get all active sessions for a user (excluding expired)"""
        now = datetime.now()
        return (
            db.query(ActiveSession)
            .filter(
                ActiveSession.user_id == user_id,
                (ActiveSession.expires_at.is_(None)) | (ActiveSession.expires_at > now),
            )
            .all()
        )

    @staticmethod
    def count_active_sessions_by_user(db: Session, user_id: str, exclude_session_id: str | None = None) -> int:
        """Count active sessions for a user, optionally excluding a specific session"""
        now = datetime.now()
        query = db.query(ActiveSession).filter(
            ActiveSession.user_id == user_id,
            (ActiveSession.expires_at.is_(None)) | (ActiveSession.expires_at > now),
        )

        if exclude_session_id:
            query = query.filter(ActiveSession.session_id != exclude_session_id)

        return query.count()

    @staticmethod
    def create_session(
        db: Session,
        session_id: str,
        token_id: int,
        user_id: str,
        stream_name: str,
        client_ip: str,
        protocol: str,
        auth_duration: int = 180,
    ) -> ActiveSession:
        """Create a new active session"""
        now = datetime.now()
        expires_at = now + timedelta(seconds=auth_duration)

        db_session = ActiveSession(
            session_id=session_id,
            token_id=token_id,
            user_id=user_id,
            stream_name=stream_name,
            client_ip=client_ip,
            protocol=protocol,
            started_at=now,
            last_checked_at=now,
            expires_at=expires_at,
        )

        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        return db_session

    @staticmethod
    def update_session_last_check(db: Session, session_id: str, auth_duration: int = 180) -> ActiveSession | None:
        """Update session's last checked timestamp and extend expiration"""
        db_session = SessionService.get_by_session_id(db, session_id)
        if not db_session:
            return None

        now = datetime.now()
        db_session.last_checked_at = now
        db_session.expires_at = now + timedelta(seconds=auth_duration)

        db.commit()
        db.refresh(db_session)
        return db_session

    @staticmethod
    def delete_session(db: Session, session_id: str) -> bool:
        """Delete a session"""
        db_session = SessionService.get_by_session_id(db, session_id)
        if not db_session:
            return False

        db.delete(db_session)
        db.commit()
        return True

    @staticmethod
    def cleanup_expired_sessions(db: Session) -> int:
        """Delete all expired sessions and return count deleted"""
        now = datetime.now()
        expired = db.query(ActiveSession).filter(
            ActiveSession.expires_at.isnot(None),
            ActiveSession.expires_at < now,
        )

        count = expired.count()
        expired.delete(synchronize_session=False)
        db.commit()

        return count

    @staticmethod
    def list_sessions(
        db: Session,
        user_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ActiveSession]:
        """List active sessions with optional user filtering"""
        query = db.query(ActiveSession)

        if user_id:
            query = query.filter(ActiveSession.user_id == user_id)

        return query.order_by(ActiveSession.started_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def get_oldest_session_for_user(db: Session, user_id: str) -> ActiveSession | None:
        """Get the oldest session for a user (for potential termination)"""
        return (
            db.query(ActiveSession)
            .filter(ActiveSession.user_id == user_id)
            .order_by(ActiveSession.started_at.asc())
            .first()
        )
