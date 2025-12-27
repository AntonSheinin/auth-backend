"""Session service for managing active streaming sessions."""

from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DatabaseError, SessionNotFoundError
from app.models.session import ActiveSession


class SessionService:
    """Service for session-related database operations.

    Note: Methods do NOT commit transactions unless explicitly stated.
    The caller (typically route handlers or validation service) is responsible
    for transaction management.
    """

    @staticmethod
    async def get_by_session_id(db: AsyncSession, session_id: str) -> ActiveSession | None:
        """Get session by session ID.

        Args:
            db: Database session
            session_id: Session ID to search for

        Returns:
            ActiveSession model or None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            result = await db.execute(select(ActiveSession).filter(ActiveSession.session_id == session_id))
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            raise DatabaseError("get_by_session_id", e) from e

    @staticmethod
    async def get_active_sessions_by_user(db: AsyncSession, user_id: str) -> list[ActiveSession]:
        """Get all active sessions for a user (excluding expired).

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            List of ActiveSession models

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            now = datetime.now()
            result = await db.execute(
                select(ActiveSession).filter(
                    ActiveSession.user_id == user_id,
                    (ActiveSession.expires_at.is_(None)) | (ActiveSession.expires_at > now),
                )
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            raise DatabaseError("get_active_sessions_by_user", e) from e

    @staticmethod
    async def get_active_sessions_for_update(
        db: AsyncSession, user_id: str, exclude_session_id: str | None = None
    ) -> list[ActiveSession]:
        """Get active sessions with row-level lock (SELECT FOR UPDATE).

        This method is used to prevent race conditions when checking session limits.
        It locks the rows, preventing concurrent inserts from bypassing the limit check.

        Args:
            db: Database session
            user_id: User ID to get sessions for
            exclude_session_id: Optional session ID to exclude

        Returns:
            List of ActiveSession models (locked for update)

        Raises:
            DatabaseError: If database operation fails

        Note:
            This must be called within a transaction. The locks are released when
            the transaction commits or rolls back.
        """
        try:
            now = datetime.now()
            query = select(ActiveSession).filter(
                ActiveSession.user_id == user_id,
                (ActiveSession.expires_at.is_(None)) | (ActiveSession.expires_at > now),
            )

            if exclude_session_id:
                query = query.filter(ActiveSession.session_id != exclude_session_id)

            # Lock the rows to prevent concurrent inserts
            query = query.with_for_update()

            result = await db.execute(query)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            raise DatabaseError("get_active_sessions_for_update", e) from e

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
        """Create a new active session.

        Args:
            db: Database session
            session_id: Unique session identifier
            token_id: Foreign key to token
            user_id: User identifier
            stream_name: Stream name being accessed
            client_ip: Client IP address
            protocol: Protocol used (hls, rtmp, etc.)
            auth_duration: Session duration in seconds

        Returns:
            Created ActiveSession model

        Raises:
            DatabaseError: If database operation fails

        Note:
            This method does NOT commit. Caller must commit the transaction.
        """
        try:
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
            await db.flush()
            await db.refresh(db_session)
            return db_session
        except SQLAlchemyError as e:
            raise DatabaseError("create_session", e) from e

    @staticmethod
    async def update_session_last_check(
        db: AsyncSession, session_id: str, auth_duration: int = 180
    ) -> ActiveSession:
        """Update session's last checked timestamp and extend expiration.

        Args:
            db: Database session
            session_id: Session ID to update
            auth_duration: Duration to extend session by

        Returns:
            Updated ActiveSession model

        Raises:
            SessionNotFoundError: If session not found
            DatabaseError: If database operation fails

        Note:
            This method does NOT commit. Caller must commit the transaction.
        """
        try:
            db_session = await SessionService.get_by_session_id(db, session_id)
            if not db_session:
                raise SessionNotFoundError(session_id)

            now = datetime.now()
            db_session.last_checked_at = now
            db_session.expires_at = now + timedelta(seconds=auth_duration)

            await db.flush()
            await db.refresh(db_session)
            return db_session
        except SessionNotFoundError:
            raise
        except SQLAlchemyError as e:
            raise DatabaseError("update_session_last_check", e) from e

    @staticmethod
    async def delete_session(db: AsyncSession, session_id: str) -> None:
        """Delete a session by session_id string.

        Args:
            db: Database session
            session_id: Session ID to delete

        Raises:
            SessionNotFoundError: If session not found
            DatabaseError: If database operation fails

        Note:
            This method does NOT commit. Caller must commit the transaction.
        """
        try:
            db_session = await SessionService.get_by_session_id(db, session_id)
            if not db_session:
                raise SessionNotFoundError(session_id)

            await db.delete(db_session)
            await db.flush()
        except SessionNotFoundError:
            raise
        except SQLAlchemyError as e:
            raise DatabaseError("delete_session", e) from e

    @staticmethod
    async def delete_session_by_id(db: AsyncSession, session_db_id: int) -> None:
        """Delete a session by database ID.

        Args:
            db: Database session
            session_db_id: Database ID of the session to delete

        Raises:
            DatabaseError: If database operation fails

        Note:
            This method does NOT commit. Caller must commit the transaction.
        """
        try:
            result = await db.execute(
                select(ActiveSession).filter(ActiveSession.id == session_db_id)
            )
            db_session = result.scalar_one_or_none()
            if db_session:
                await db.delete(db_session)
                await db.flush()
        except SQLAlchemyError as e:
            raise DatabaseError("delete_session_by_id", e) from e

    @staticmethod
    async def cleanup_expired_sessions(db: AsyncSession) -> int:
        """Delete all expired sessions using bulk operation.

        Args:
            db: Database session

        Returns:
            Number of sessions deleted

        Raises:
            DatabaseError: If database operation fails

        Note:
            This method DOES commit the transaction (used by background task).
        """
        try:
            now = datetime.now()

            # Use bulk delete for better performance
            delete_query = delete(ActiveSession).filter(
                ActiveSession.expires_at.isnot(None),
                ActiveSession.expires_at < now,
            )
            result = await db.execute(delete_query)
            await db.commit()

            return result.rowcount or 0
        except SQLAlchemyError as e:
            await db.rollback()
            raise DatabaseError("cleanup_expired_sessions", e) from e

    @staticmethod
    async def list_sessions(
        db: AsyncSession,
        user_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ActiveSession]:
        """List active sessions with optional user filtering.

        Args:
            db: Database session
            user_id: Optional user ID filter
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of ActiveSession models

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = select(ActiveSession)

            if user_id:
                query = query.filter(ActiveSession.user_id == user_id)

            query = query.order_by(ActiveSession.started_at.desc()).offset(skip).limit(limit)
            result = await db.execute(query)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            raise DatabaseError("list_sessions", e) from e
