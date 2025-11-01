"""Custom exception classes for the application."""

from typing import Any


class AuthBackendError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class TokenNotFoundError(AuthBackendError):
    """Token not found in database."""

    def __init__(self, token: str) -> None:
        super().__init__(
            message="Token not found",
            details={"token_preview": token[:10] + "..." if len(token) > 10 else token},
        )


class TokenAlreadyExistsError(AuthBackendError):
    """Token already exists in database."""

    def __init__(self, token: str) -> None:
        super().__init__(
            message="Token already exists",
            details={"token_preview": token[:10] + "..." if len(token) > 10 else token},
        )


class SessionNotFoundError(AuthBackendError):
    """Session not found in database."""

    def __init__(self, session_id: str) -> None:
        super().__init__(
            message="Session not found",
            details={"session_id": session_id[:10] + "..." if len(session_id) > 10 else session_id},
        )


class DatabaseError(AuthBackendError):
    """Database operation failed."""

    def __init__(self, operation: str, original_error: Exception) -> None:
        super().__init__(
            message=f"Database operation failed: {operation}",
            details={"error": str(original_error), "error_type": type(original_error).__name__},
        )
        self.original_error = original_error


class ValidationError(AuthBackendError):
    """Input validation failed."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message=f"Validation error for {field}: {message}", details={"field": field})
