"""Enumerations used throughout the application."""

from enum import Enum


class TokenStatus(str, Enum):
    """Token status enumeration."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


class AccessResult(str, Enum):
    """Access log result enumeration."""

    ALLOWED = "allowed"
    DENIED = "denied"
