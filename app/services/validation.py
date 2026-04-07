"""Validation service for authorization logic."""

import asyncio
import logging
from datetime import datetime

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.enums import AccessResult, TokenStatus
from app.exceptions import DatabaseError
from app.models.token import Token
from app.services.access_log_service import AccessLogService
from app.services.session_service import SessionService
from app.services.token_service import TokenService
from app.utils.session_id import generate_session_id

logger = logging.getLogger(__name__)


class ValidationService:
    """Service for authorization validation logic with proper transaction management."""

    @staticmethod
    def _is_duplicate_session_insert(error: DatabaseError) -> bool:
        """Check whether a DatabaseError came from duplicate session_id insertion."""
        original = getattr(error, "original_error", None)
        if not isinstance(original, IntegrityError):
            return False

        # Keep this broad across supported DBs/drivers (PostgreSQL/MySQL/SQLite).
        message = str(original).lower()
        return "duplicate" in message and "session_id" in message

    @staticmethod
    async def validate_authorization(
        db: AsyncSession,
        stream_name: str,
        client_ip: str,
        token: str,
        protocol: str,
        settings: Settings,
    ) -> tuple[bool, str | None, Token | None]:
        """Validate authorization request from Flussonic with race condition prevention.

        This method uses SELECT FOR UPDATE to lock rows and prevent concurrent
        sessions from exceeding the limit. The entire validation is wrapped in
        a transaction that commits only on success.

        Args:
            db: Database session
            stream_name: Stream name being accessed
            client_ip: Client IP address
            token: Authorization token string
            protocol: Protocol used (hls, rtmp, etc.)
            settings: Application settings

        Returns:
            Tuple of (is_allowed, denial_reason, token_object)
            - is_allowed: True if access is granted
            - denial_reason: Reason string if denied, None if allowed
            - token_object: Token model if found, None otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            # 1. Look up token
            token_obj = await TokenService.get_by_token(db, token)
            if not token_obj:
                await AccessLogService.log_access(
                    db, token, None, stream_name, client_ip, protocol,
                    AccessResult.DENIED, "token_not_found", settings
                )
                await db.commit()
                return False, "token_not_found", None

            # 2. Check token status - must be explicitly ACTIVE
            logger.info(f"Token status check: token_id={token_obj.id}, status='{token_obj.status}', expected_active='{TokenStatus.ACTIVE.value}'")
            if token_obj.status != TokenStatus.ACTIVE.value:
                # Determine specific denial reason based on status
                if token_obj.status == TokenStatus.SUSPENDED.value:
                    denial_reason = "token_suspended"
                elif token_obj.status == TokenStatus.EXPIRED.value:
                    denial_reason = "token_expired"
                else:
                    denial_reason = "token_invalid_status"

                logger.warning(f"Token denied: status='{token_obj.status}', reason={denial_reason}")
                await AccessLogService.log_access(
                    db, token, token_obj.user_id, stream_name, client_ip, protocol,
                    AccessResult.DENIED, denial_reason, settings
                )
                await db.commit()
                return False, denial_reason, token_obj

            # 3. Check validity period
            now = datetime.now()
            if now < token_obj.valid_from:
                await AccessLogService.log_access(
                    db, token, token_obj.user_id, stream_name, client_ip, protocol,
                    AccessResult.DENIED, "token_not_yet_valid", settings
                )
                await db.commit()
                return False, "token_not_yet_valid", token_obj

            if token_obj.valid_until and now > token_obj.valid_until:
                # Auto-expire the token
                await TokenService.update_token(db, token_obj.id, status=TokenStatus.EXPIRED)
                await AccessLogService.log_access(
                    db, token, token_obj.user_id, stream_name, client_ip, protocol,
                    AccessResult.DENIED, "token_expired", settings
                )
                await db.commit()
                return False, "token_expired", token_obj

            # 4. Check IP whitelist
            allowed_ips = token_obj.get_allowed_ips()
            if allowed_ips and client_ip not in allowed_ips:
                await AccessLogService.log_access(
                    db, token, token_obj.user_id, stream_name, client_ip, protocol,
                    AccessResult.DENIED, "ip_not_allowed", settings
                )
                await db.commit()
                return False, "ip_not_allowed", token_obj

            # 5. Check stream whitelist
            allowed_streams = token_obj.get_allowed_streams()
            if allowed_streams and stream_name not in allowed_streams:
                await AccessLogService.log_access(
                    db, token, token_obj.user_id, stream_name, client_ip, protocol,
                    AccessResult.DENIED, "stream_not_allowed", settings
                )
                await db.commit()
                return False, "stream_not_allowed", token_obj

            token_user_id = token_obj.user_id
            token_id = token_obj.id

            # 6. Check concurrent sessions limit with proper locking
            session_id = generate_session_id(
                stream_name,
                client_ip,
                token,
            )
            existing_session = await SessionService.get_by_session_id(db, session_id)

            if existing_session:
                # This is a re-check (Flussonic checks every 3 minutes)
                # Token status has already been validated above (suspended/expired checks)
                # so we can safely extend the session
                await SessionService.update_session_last_check(db, session_id, settings.auth_duration)
                await AccessLogService.log_access(
                    db, token, token_user_id, stream_name, client_ip, protocol,
                    AccessResult.ALLOWED, "session_recheck", settings
                )
                await db.commit()
                return True, None, token_obj
            else:
                # New session attempt - CRITICAL: Use SELECT FOR UPDATE to prevent race conditions
                # Lock existing sessions for this user to prevent concurrent insertions
                active_sessions = await SessionService.get_active_sessions_for_update(
                    db, token_user_id, exclude_session_id=session_id
                )

                # Channel switch handling: for the same token+IP, keep only the latest stream session.
                # This prevents "can't switch channel" when old stream sessions are still alive.
                sessions_from_same_source = [
                    s for s in active_sessions
                    if s.client_ip == client_ip and s.token_id == token_id
                ]

                for old_session in sessions_from_same_source:
                    logger.info(
                        "Channel switch detected: replacing old session "
                        f"(user={token_user_id}, ip={client_ip}, old_stream={old_session.stream_name}, "
                        f"new_stream={stream_name})"
                    )
                    await SessionService.delete_session_by_id(db, old_session.id)

                remaining_sessions = [s for s in active_sessions if s not in sessions_from_same_source]
                active_count = len(remaining_sessions)

                if active_count >= token_obj.max_sessions:
                    await AccessLogService.log_access(
                        db, token, token_user_id, stream_name, client_ip, protocol,
                        AccessResult.DENIED,
                        f"max_sessions_reached ({active_count}/{token_obj.max_sessions})",
                        settings
                    )
                    await db.commit()
                    return False, "max_sessions_reached", token_obj

                # Create new session within the same transaction (locks held until commit).
                # If a concurrent identical request inserts first, treat duplicate insert as recheck.
                try:
                    await SessionService.create_session(
                        db=db,
                        session_id=session_id,
                        token_id=token_id,
                        user_id=token_user_id,
                        stream_name=stream_name,
                        client_ip=client_ip,
                        protocol=protocol,
                        auth_duration=settings.auth_duration,
                    )

                    await AccessLogService.log_access(
                        db, token, token_user_id, stream_name, client_ip, protocol,
                        AccessResult.ALLOWED, "new_session", settings
                    )
                    await db.commit()
                    return True, None, token_obj
                except DatabaseError as e:
                    if not ValidationService._is_duplicate_session_insert(e):
                        raise

                    # The transaction is aborted after integrity errors; reset it before re-reading.
                    await db.rollback()
                    logger.info(
                        "Concurrent session insert detected; converting to session_recheck "
                        f"(user={token_user_id}, stream={stream_name}, ip={client_ip})"
                    )

                    # Winner transaction may not be committed yet, so poll briefly.
                    for _ in range(5):
                        concurrent_session = await SessionService.get_by_session_id(db, session_id)
                        if concurrent_session:
                            await SessionService.update_session_last_check(db, session_id, settings.auth_duration)
                            await AccessLogService.log_access(
                                db, token, token_user_id, stream_name, client_ip, protocol,
                                AccessResult.ALLOWED, "session_recheck", settings
                            )
                            await db.commit()
                            return True, None, token_obj
                        await asyncio.sleep(0.05)

                    # If still not visible, retry creation once on a clean transaction.
                    await SessionService.create_session(
                        db=db,
                        session_id=session_id,
                        token_id=token_id,
                        user_id=token_user_id,
                        stream_name=stream_name,
                        client_ip=client_ip,
                        protocol=protocol,
                        auth_duration=settings.auth_duration,
                    )
                    await AccessLogService.log_access(
                        db, token, token_user_id, stream_name, client_ip, protocol,
                        AccessResult.ALLOWED, "new_session", settings
                    )
                    await db.commit()
                    return True, None, token_obj

        except (DatabaseError, SQLAlchemyError) as e:
            # Rollback on any database error to maintain consistency
            await db.rollback()
            logger.error(
                f"Database error during authorization validation: {e}",
                extra={
                    "stream_name": stream_name,
                    "client_ip": client_ip,
                    "token_preview": token[:8] + "..." if len(token) > 8 else token,
                },
                exc_info=True,
            )
            raise DatabaseError("validate_authorization", e) from e
        except Exception as e:
            # Rollback on any unexpected error
            await db.rollback()
            logger.error(
                f"Unexpected error during authorization validation: {e}",
                extra={
                    "stream_name": stream_name,
                    "client_ip": client_ip,
                },
                exc_info=True,
            )
            raise
