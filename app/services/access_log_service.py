"""Access logging service for authorization attempts."""

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.enums import AccessResult
from app.exceptions import DatabaseError
from app.models.log import AccessLog

logger = logging.getLogger(__name__)


class AccessLogService:
    """Service for logging access attempts to database."""

    @staticmethod
    async def log_access(
        db: AsyncSession,
        token: str,
        user_id: str | None,
        stream_name: str,
        client_ip: str,
        protocol: str,
        result: AccessResult,
        reason: str,
        settings: Settings,
    ) -> None:
        """Log access attempt to database if logging is enabled.

        Args:
            db: Database session
            token: Token string (will be masked in logs)
            user_id: User identifier if token was found
            stream_name: Stream name being accessed
            client_ip: Client IP address
            protocol: Protocol used (hls, rtmp, etc.)
            result: Access result (allowed/denied)
            reason: Reason for the result
            settings: Application settings

        Note:
            This method does NOT commit the transaction. The caller is responsible
            for committing or rolling back the transaction.
        """
        if not settings.enable_access_logs:
            return

        try:
            log_entry = AccessLog(
                token=token,
                user_id=user_id,
                stream_name=stream_name,
                client_ip=client_ip,
                protocol=protocol,
                result=result.value,
                reason=reason,
            )
            db.add(log_entry)
            # Note: No commit here - let the caller control the transaction
        except Exception as e:
            # Don't fail the authorization due to logging errors
            logger.error(f"Failed to create access log entry: {e}", exc_info=True)

    @staticmethod
    async def log_and_commit(
        db: AsyncSession,
        token: str,
        user_id: str | None,
        stream_name: str,
        client_ip: str,
        protocol: str,
        result: AccessResult,
        reason: str,
        settings: Settings,
    ) -> None:
        """Log access attempt and commit immediately.

        This is a convenience method for cases where immediate logging is needed.
        Use log_access() instead when managing transactions manually.

        Args:
            db: Database session
            token: Token string
            user_id: User identifier if token was found
            stream_name: Stream name being accessed
            client_ip: Client IP address
            protocol: Protocol used
            result: Access result (allowed/denied)
            reason: Reason for the result
            settings: Application settings
        """
        await AccessLogService.log_access(
            db=db,
            token=token,
            user_id=user_id,
            stream_name=stream_name,
            client_ip=client_ip,
            protocol=protocol,
            result=result,
            reason=reason,
            settings=settings,
        )
        try:
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to commit access log: {e}", exc_info=True)
            await db.rollback()

    @staticmethod
    async def cleanup_old_logs(db: AsyncSession, retention_days: int) -> int:
        """Delete access logs older than retention_days.

        Args:
            db: Database session
            retention_days: Number of days to retain logs

        Returns:
            Number of logs deleted

        Raises:
            DatabaseError: If database operation fails

        Note:
            This method DOES commit the transaction (used by background task).
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)

            # First count how many logs will be deleted
            count_query = select(func.count()).select_from(AccessLog).filter(AccessLog.timestamp < cutoff_date)
            count_result = await db.execute(count_query)
            count = count_result.scalar() or 0

            # Delete old logs using bulk delete
            delete_query = delete(AccessLog).filter(AccessLog.timestamp < cutoff_date)
            await db.execute(delete_query)
            await db.commit()

            return count
        except SQLAlchemyError as e:
            await db.rollback()
            raise DatabaseError("cleanup_old_logs", e) from e

    @staticmethod
    async def list_access_logs(
        db: AsyncSession,
        user_id: str | None = None,
        token: str | None = None,
        stream_name: str | None = None,
        client_ip: str | None = None,
        protocol: str | None = None,
        result: AccessResult | None = None,
        reason: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AccessLog]:
        """List access logs with optional filters.

        Args:
            db: Database session
            user_id: Optional user identifier filter
            token: Optional token filter
            stream_name: Optional stream name filter
            client_ip: Optional client IP filter
            protocol: Optional protocol filter
            result: Optional access result filter
            reason: Optional reason filter
            start_time: Optional start timestamp (inclusive)
            end_time: Optional end timestamp (inclusive)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of AccessLog models

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = select(AccessLog)

            if user_id:
                query = query.filter(AccessLog.user_id == user_id)
            if token:
                query = query.filter(AccessLog.token == token)
            if stream_name:
                query = query.filter(AccessLog.stream_name == stream_name)
            if client_ip:
                query = query.filter(AccessLog.client_ip == client_ip)
            if protocol:
                query = query.filter(AccessLog.protocol == protocol)
            if result:
                query = query.filter(AccessLog.result == result)
            if reason:
                query = query.filter(AccessLog.reason == reason)
            if start_time:
                query = query.filter(AccessLog.timestamp >= start_time)
            if end_time:
                query = query.filter(AccessLog.timestamp <= end_time)

            query = query.order_by(AccessLog.timestamp.desc()).offset(skip).limit(limit)
            result_proxy = await db.execute(query)
            return list(result_proxy.scalars().all())
        except SQLAlchemyError as e:
            raise DatabaseError("list_access_logs", e) from e
