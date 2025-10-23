"""Logging configuration."""

import logging

from app.config import get_settings


def setup_logging() -> None:
    """Configure application logging using Python defaults."""
    settings = get_settings()

    # Use default basicConfig with console output only
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
