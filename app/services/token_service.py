"""Token service for database operations"""
from sqlalchemy.orm import Session
from app.models.token import Token
from typing import Optional, List
from datetime import datetime


class TokenService:
    """Service for token-related database operations"""

    @staticmethod
    def get_by_token(db: Session, token: str) -> Optional[Token]:
        """Get token by token string"""
        return db.query(Token).filter(Token.token == token).first()

    @staticmethod
    def get_by_id(db: Session, token_id: int) -> Optional[Token]:
        """Get token by ID"""
        return db.query(Token).filter(Token.id == token_id).first()

    @staticmethod
    def get_by_user_id(db: Session, user_id: str) -> List[Token]:
        """Get all tokens for a user"""
        return db.query(Token).filter(Token.user_id == user_id).all()

    @staticmethod
    def create_token(
        db: Session,
        token: str,
        user_id: str,
        status: str = "active",
        max_sessions: int = 1,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
        allowed_ips: Optional[List[str]] = None,
        allowed_streams: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
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
        if metadata:
            db_token.set_meta(metadata)

        db.add(db_token)
        db.commit()
        db.refresh(db_token)
        return db_token

    @staticmethod
    def update_token(db: Session, token_id: int, **kwargs) -> Optional[Token]:
        """Update token fields"""
        db_token = TokenService.get_by_id(db, token_id)
        if not db_token:
            return None

        # Update allowed fields
        for key, value in kwargs.items():
            if value is not None:
                if key == "allowed_ips" and isinstance(value, list):
                    db_token.set_allowed_ips(value)
                elif key == "allowed_streams" and isinstance(value, list):
                    db_token.set_allowed_streams(value)
                elif key == "metadata" and isinstance(value, dict):
                    db_token.set_meta(value)
                elif hasattr(db_token, key):
                    setattr(db_token, key, value)

        db_token.updated_at = datetime.now()
        db.commit()
        db.refresh(db_token)
        return db_token

    @staticmethod
    def delete_token(db: Session, token_id: int) -> bool:
        """Delete a token"""
        db_token = TokenService.get_by_id(db, token_id)
        if not db_token:
            return False

        db.delete(db_token)
        db.commit()
        return True

    @staticmethod
    def list_tokens(
        db: Session,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Token]:
        """List tokens with optional filtering"""
        query = db.query(Token)

        if status:
            query = query.filter(Token.status == status)

        return query.offset(skip).limit(limit).all()
