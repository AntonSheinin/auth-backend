"""Access logging service for authorization attempts."""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.enums import AccessResult
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
