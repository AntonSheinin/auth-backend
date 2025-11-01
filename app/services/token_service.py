"""Token service for database operations."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import TokenStatus
from app.exceptions import DatabaseError, TokenNotFoundError
from app.models.token import Token


class TokenService:
    """Service for token-related database operations.

    Note: Methods do NOT commit transactions unless explicitly stated.
    The caller (typically route handlers) is responsible for transaction management.
    """

    @staticmethod
    async def get_by_token(db: AsyncSession, token: str) -> Token | None:
        """Get token by token string.

        Args:
            db: Database session
            token: Token string to search for

        Returns:
            Token model or None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            result = await db.execute(select(Token).filter(Token.token == token))
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            raise DatabaseError("get_by_token", e) from e

    @staticmethod
    async def get_by_id(db: AsyncSession, token_id: int) -> Token | None:
        """Get token by ID.

        Args:
            db: Database session
            token_id: Token ID

        Returns:
            Token model or None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            result = await db.execute(select(Token).filter(Token.id == token_id))
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            raise DatabaseError("get_by_id", e) from e

    @staticmethod
    async def get_by_user_id(db: AsyncSession, user_id: str) -> list[Token]:
        """Get all tokens for a user.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            List of Token models (empty list if none found)

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            result = await db.execute(select(Token).filter(Token.user_id == user_id))
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            raise DatabaseError("get_by_user_id", e) from e

    @staticmethod
    async def create_token(
        db: AsyncSession,
        token: str,
        user_id: str,
        status: TokenStatus = TokenStatus.ACTIVE,
        max_sessions: int = 1,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        allowed_ips: list[str] | None = None,
        allowed_streams: list[str] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Token:
        """Create a new token.

        Args:
            db: Database session
            token: Token string
            user_id: User identifier
            status: Token status (default: active)
            max_sessions: Maximum concurrent sessions
            valid_from: Token validity start date
            valid_until: Token validity end date
            allowed_ips: List of allowed IP addresses
            allowed_streams: List of allowed stream names
            meta: Additional metadata

        Returns:
            Created Token model

        Raises:
            DatabaseError: If database operation fails

        Note:
            This method does NOT commit. Caller must commit the transaction.
        """
        try:
            db_token = Token(
                token=token,
                user_id=user_id,
                status=status.value if isinstance(status, TokenStatus) else status,
                max_sessions=max_sessions,
                valid_from=valid_from or datetime.now(),
                valid_until=valid_until,
            )

            if allowed_ips:
                db_token.set_allowed_ips(allowed_ips)
            if allowed_streams:
                db_token.set_allowed_streams(allowed_streams)
            if meta:
                db_token.set_meta(meta)

            db.add(db_token)
            await db.flush()  # Flush to get the ID, but don't commit
            await db.refresh(db_token)
            return db_token
        except SQLAlchemyError as e:
            raise DatabaseError("create_token", e) from e

    @staticmethod
    async def update_token(db: AsyncSession, token_id: int, **kwargs: Any) -> Token:
        """Update token fields.

        Args:
            db: Database session
            token_id: Token ID to update
            **kwargs: Fields to update

        Returns:
            Updated Token model

        Raises:
            TokenNotFoundError: If token not found
            DatabaseError: If database operation fails

        Note:
            This method does NOT commit. Caller must commit the transaction.
        """
        try:
            db_token = await TokenService.get_by_id(db, token_id)
            if not db_token:
                raise TokenNotFoundError(str(token_id))

            # Update allowed fields
            for key, value in kwargs.items():
                if value is not None:
                    if key == "allowed_ips" and isinstance(value, list):
                        db_token.set_allowed_ips(value)
                    elif key == "allowed_streams" and isinstance(value, list):
                        db_token.set_allowed_streams(value)
                    elif key == "meta" and isinstance(value, dict):
                        db_token.set_meta(value)
                    elif key == "status" and isinstance(value, TokenStatus):
                        db_token.status = value.value
                    elif hasattr(db_token, key):
                        setattr(db_token, key, value)

            db_token.updated_at = datetime.now()
            await db.flush()
            await db.refresh(db_token)
            return db_token
        except TokenNotFoundError:
            raise
        except SQLAlchemyError as e:
            raise DatabaseError("update_token", e) from e

    @staticmethod
    async def delete_token(db: AsyncSession, token_id: int) -> None:
        """Delete a token.

        Args:
            db: Database session
            token_id: Token ID to delete

        Raises:
            TokenNotFoundError: If token not found
            DatabaseError: If database operation fails

        Note:
            This method does NOT commit. Caller must commit the transaction.
        """
        try:
            db_token = await TokenService.get_by_id(db, token_id)
            if not db_token:
                raise TokenNotFoundError(str(token_id))

            await db.delete(db_token)
            await db.flush()
        except TokenNotFoundError:
            raise
        except SQLAlchemyError as e:
            raise DatabaseError("delete_token", e) from e

    @staticmethod
    async def list_tokens(
        db: AsyncSession,
        status: TokenStatus | str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Token]:
        """List tokens with optional filtering.

        Args:
            db: Database session
            status: Filter by token status
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of Token models

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = select(Token)

            if status:
                status_value = status.value if isinstance(status, TokenStatus) else status
                query = query.filter(Token.status == status_value)

            query = query.offset(skip).limit(limit)
            result = await db.execute(query)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            raise DatabaseError("list_tokens", e) from e
