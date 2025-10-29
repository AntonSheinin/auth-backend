"""Session service for managing active streaming sessions."""
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import ActiveSession


class SessionService:
    """Service for session-related database operations"""

    @staticmethod
    async def get_by_session_id(db: AsyncSession, session_id: str) -> ActiveSession | None:
        """Get session by session ID."""
        result = await db.execute(select(ActiveSession).filter(ActiveSession.session_id == session_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_sessions_by_user(db: AsyncSession, user_id: str) -> list[ActiveSession]:
        """Get all active sessions for a user (excluding expired)"""
        now = datetime.now()
        result = await db.execute(
            select(ActiveSession).filter(
                ActiveSession.user_id == user_id,
                (ActiveSession.expires_at.is_(None)) | (ActiveSession.expires_at > now),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_active_sessions_by_user(
        db: AsyncSession, user_id: str, exclude_session_id: str | None = None, lock_for_update: bool = False
    ) -> int:
        """Count active sessions for a user, optionally excluding a specific session.

        Args:
            db: Database session
            user_id: User ID to count sessions for
            exclude_session_id: Optional session ID to exclude from count
            lock_for_update: If True, use SELECT FOR UPDATE to prevent race conditions
        """
        now = datetime.now()
        query = select(func.count()).select_from(ActiveSession).filter(
            ActiveSession.user_id == user_id,
            (ActiveSession.expires_at.is_(None)) | (ActiveSession.expires_at > now),
        )

        if exclude_session_id:
            query = query.filter(ActiveSession.session_id != exclude_session_id)

        # Add row-level locking to prevent concurrent insertions
        if lock_for_update:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar() or 0

    @staticmethod
    async def create_session(
        db: AsyncSession,
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
        await db.commit()
        await db.refresh(db_session)
        return db_session

    @staticmethod
    async def update_session_last_check(
        db: AsyncSession, session_id: str, auth_duration: int = 180
    ) -> ActiveSession | None:
        """Update session's last checked timestamp and extend expiration"""
        db_session = await SessionService.get_by_session_id(db, session_id)
        if not db_session:
            return None

        now = datetime.now()
        db_session.last_checked_at = now
        db_session.expires_at = now + timedelta(seconds=auth_duration)

        await db.commit()
        await db.refresh(db_session)
        return db_session

    @staticmethod
    async def delete_session(db: AsyncSession, session_id: str) -> bool:
        """Delete a session"""
        db_session = await SessionService.get_by_session_id(db, session_id)
        if not db_session:
            return False

        await db.delete(db_session)
        await db.commit()
        return True

    @staticmethod
    async def cleanup_expired_sessions(db: AsyncSession) -> int:
        """Delete all expired sessions and return count deleted"""
        now = datetime.now()

        # First count the expired sessions
        count_query = select(func.count()).select_from(ActiveSession).filter(
            ActiveSession.expires_at.isnot(None),
            ActiveSession.expires_at < now,
        )
        result = await db.execute(count_query)
        count = result.scalar() or 0

        # Delete expired sessions
        delete_query = delete(ActiveSession).filter(
            ActiveSession.expires_at.isnot(None),
            ActiveSession.expires_at < now,
        )
        await db.execute(delete_query)
        await db.commit()

        return count

    @staticmethod
    async def list_sessions(
        db: AsyncSession,
        user_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ActiveSession]:
        """List active sessions with optional user filtering"""
        query = select(ActiveSession)

        if user_id:
            query = query.filter(ActiveSession.user_id == user_id)

        query = query.order_by(ActiveSession.started_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_oldest_session_for_user(db: AsyncSession, user_id: str) -> ActiveSession | None:
        """Get the oldest session for a user (for potential termination)"""
        result = await db.execute(
            select(ActiveSession).filter(ActiveSession.user_id == user_id).order_by(ActiveSession.started_at.asc())
        )
        return result.scalar_one_or_none()
