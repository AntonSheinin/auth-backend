"""SQLAlchemy declarative base - isolated to prevent circular imports."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass
