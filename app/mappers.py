"""Mappers for converting ORM models to response schemas."""

from app.models.token import Token
from app.schemas.management import TokenResponse


class TokenMapper:
    """Mapper for Token model to response schemas."""

    @staticmethod
    def to_response(token: Token) -> TokenResponse:
        """Convert Token ORM model to TokenResponse schema.

        Args:
            token: Token ORM model instance

        Returns:
            TokenResponse schema with parsed JSON fields
        """
        return TokenResponse(
            id=token.id,
            token=token.token,
            user_id=token.user_id,
            status=token.status,
            max_sessions=token.max_sessions,
            valid_from=token.valid_from,
            valid_until=token.valid_until,
            allowed_ips=token.get_allowed_ips(),
            allowed_streams=token.get_allowed_streams(),
            meta=token.get_meta(),
            created_at=token.created_at,
            updated_at=token.updated_at,
        )

    @staticmethod
    def to_response_list(tokens: list[Token]) -> list[TokenResponse]:
        """Convert list of Token models to list of TokenResponse schemas.

        Args:
            tokens: List of Token ORM model instances

        Returns:
            List of TokenResponse schemas
        """
        return [TokenMapper.to_response(token) for token in tokens]
