"""Validation service for authorization logic."""

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.log import AccessLog
from app.models.token import Token
from app.services.session_service import SessionService
from app.services.token_service import TokenService
from app.utils.session_id import generate_session_id

logger = logging.getLogger(__name__)
settings = get_settings()


class ValidationService:
    """Service for authorization validation logic."""

    @staticmethod
    async def validate_authorization(
        db: AsyncSession,
        stream_name: str,
        client_ip: str,
        token: str,
        protocol: str = "unknown",
    ) -> tuple[bool, str | None, Token | None]:
        """
        Validate authorization request from Flussonic

        Returns:
            Tuple of (is_allowed, denial_reason, token_object)
        """

        # 1. Look up token
        token_obj = await TokenService.get_by_token(db, token)
        if not token_obj:
            await ValidationService._log_access(
                db, token, None, stream_name, client_ip, protocol, "denied", "token_not_found"
            )
            return False, "token_not_found", None

        # 2. Check token status
        if token_obj.status == "suspended":
            await ValidationService._log_access(
                db, token, token_obj.user_id, stream_name, client_ip, protocol, "denied", "token_suspended"
            )
            return False, "token_suspended", token_obj

        if token_obj.status == "expired":
            await ValidationService._log_access(
                db, token, token_obj.user_id, stream_name, client_ip, protocol, "denied", "token_expired"
            )
            return False, "token_expired", token_obj

        # 3. Check validity period
        now = datetime.now()
        if now < token_obj.valid_from:
            await ValidationService._log_access(
                db, token, token_obj.user_id, stream_name, client_ip, protocol, "denied", "token_not_yet_valid"
            )
            return False, "token_not_yet_valid", token_obj

        if token_obj.valid_until and now > token_obj.valid_until:
            # Auto-expire the token
            await TokenService.update_token(db, token_obj.id, status="expired")
            await ValidationService._log_access(
                db, token, token_obj.user_id, stream_name, client_ip, protocol, "denied", "token_expired"
            )
            return False, "token_expired", token_obj

        # 4. Check IP whitelist
        allowed_ips = token_obj.get_allowed_ips()
        if allowed_ips and client_ip not in allowed_ips:
            await ValidationService._log_access(
                db, token, token_obj.user_id, stream_name, client_ip, protocol, "denied", "ip_not_allowed"
            )
            return False, "ip_not_allowed", token_obj

        # 5. Check stream whitelist
        allowed_streams = token_obj.get_allowed_streams()
        if allowed_streams and stream_name not in allowed_streams:
            await ValidationService._log_access(
                db, token, token_obj.user_id, stream_name, client_ip, protocol, "denied", "stream_not_allowed"
            )
            return False, "stream_not_allowed", token_obj

        # 6. Check concurrent sessions limit
        session_id = generate_session_id(stream_name, client_ip, token)
        existing_session = await SessionService.get_by_session_id(db, session_id)

        if existing_session:
            # This is a re-check (Flussonic checks every 3 minutes)
            await SessionService.update_session_last_check(db, session_id, settings.auth_duration)
            await ValidationService._log_access(
                db, token, token_obj.user_id, stream_name, client_ip, protocol, "allowed", "session_recheck"
            )
            return True, None, token_obj
        else:
            # New session attempt - check limit with transaction isolation
            # Use SELECT FOR UPDATE to lock the user's session rows and prevent race conditions
            try:
                # Begin a nested transaction for atomic check-and-insert
                active_count = await SessionService.count_active_sessions_by_user(
                    db, token_obj.user_id, exclude_session_id=session_id, lock_for_update=True
                )

                if active_count >= token_obj.max_sessions:
                    await ValidationService._log_access(
                        db,
                        token,
                        token_obj.user_id,
                        stream_name,
                        client_ip,
                        protocol,
                        "denied",
                        f"max_sessions_reached ({active_count}/{token_obj.max_sessions})",
                    )
                    return False, "max_sessions_reached", token_obj

                # Create new session within the same transaction
                await SessionService.create_session(
                    db=db,
                    session_id=session_id,
                    token_id=token_obj.id,
                    user_id=token_obj.user_id,
                    stream_name=stream_name,
                    client_ip=client_ip,
                    protocol=protocol,
                    auth_duration=settings.auth_duration,
                )

                await ValidationService._log_access(
                    db, token, token_obj.user_id, stream_name, client_ip, protocol, "allowed", "new_session"
                )
                return True, None, token_obj
            except Exception as e:
                # Rollback on any error to maintain consistency
                await db.rollback()
                logger.error(f"Error creating session for user {token_obj.user_id}: {e}")
                raise

    @staticmethod
    async def _log_access(
        db: AsyncSession,
        token: str,
        user_id: str | None,
        stream_name: str,
        client_ip: str,
        protocol: str,
        result: str,
        reason: str,
    ) -> None:
        """Log access attempt to database if logging is enabled"""
        if not settings.enable_access_logs:
            return

        log_entry = AccessLog(
            token=token,
            user_id=user_id,
            stream_name=stream_name,
            client_ip=client_ip,
            protocol=protocol,
            result=result,
            reason=reason,
        )

        db.add(log_entry)
        await db.commit()
