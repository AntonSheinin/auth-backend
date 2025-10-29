"""Token service for database operations"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import Token


class TokenService:
    """Service for token-related database operations"""

    @staticmethod
    async def get_by_token(db: AsyncSession, token: str) -> Token | None:
        """Get token by token string"""
        result = await db.execute(select(Token).filter(Token.token == token))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(db: AsyncSession, token_id: int) -> Token | None:
        """Get token by ID"""
        result = await db.execute(select(Token).filter(Token.id == token_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_user_id(db: AsyncSession, user_id: str) -> list[Token]:
        """Get all tokens for a user"""
        result = await db.execute(select(Token).filter(Token.user_id == user_id))
        return list(result.scalars().all())

    @staticmethod
    async def create_token(
        db: AsyncSession,
        token: str,
        user_id: str,
        status: str = "active",
        max_sessions: int = 1,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        allowed_ips: list[str] | None = None,
        allowed_streams: list[str] | None = None,
        meta: dict | None = None,
    ) -> Token:
        """Create a new token"""
        db_token = Token(
            token=token,
            user_id=user_id,
            status=status,
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
        await db.commit()
        await db.refresh(db_token)
        return db_token

    @staticmethod
    async def update_token(db: AsyncSession, token_id: int, **kwargs) -> Token | None:
        """Update token fields"""
        db_token = await TokenService.get_by_id(db, token_id)
        if not db_token:
            return None

        # Update allowed fields
        for key, value in kwargs.items():
            if value is not None:
                if key == "allowed_ips" and isinstance(value, list):
                    db_token.set_allowed_ips(value)
                elif key == "allowed_streams" and isinstance(value, list):
                    db_token.set_allowed_streams(value)
                elif key == "meta" and isinstance(value, dict):
                    db_token.set_meta(value)
                elif hasattr(db_token, key):
                    setattr(db_token, key, value)

        db_token.updated_at = datetime.now()
        await db.commit()
        await db.refresh(db_token)
        return db_token

    @staticmethod
    async def delete_token(db: AsyncSession, token_id: int) -> bool:
        """Delete a token"""
        db_token = await TokenService.get_by_id(db, token_id)
        if not db_token:
            return False

        await db.delete(db_token)
        await db.commit()
        return True

    @staticmethod
    async def list_tokens(
        db: AsyncSession,
        status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Token]:
        """List tokens with optional filtering"""
        query = select(Token)

        if status:
            query = query.filter(Token.status == status)

        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())
