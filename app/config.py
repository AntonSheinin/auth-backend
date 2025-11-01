"""Configuration settings for the auth backend."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with modern Pydantic v2 configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./data/tokens.db",
        description="Database connection URL",
    )
    db_pool_size: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Database connection pool size",
    )
    db_max_overflow: int = Field(
        default=10,
        ge=0,
        le=100,
        description="Maximum overflow connections beyond pool_size",
    )
    db_pool_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Seconds to wait before timing out on getting a connection from pool",
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        v = v.strip()
        valid_prefixes = ("sqlite://", "postgresql://", "postgresql+", "mysql://", "mysql+")
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            raise ValueError(
                f"Invalid database URL. Must start with one of: {', '.join(valid_prefixes)}"
            )
        return v

    # Auth settings
    auth_duration: int = Field(
        default=180,
        ge=30,
        le=3600,
        description="Default X-AuthDuration in seconds (3 minutes)",
    )
    session_cleanup_interval: int = Field(
        default=60,
        ge=10,
        le=600,
        description="Cleanup expired sessions interval in seconds",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Logging level",
    )
    enable_access_logs: bool = Field(
        default=True,
        description="Enable access logging to database",
    )

    # API settings
    api_host: str = Field(
        default="0.0.0.0",
        description="API host binding",
    )
    api_port: int = Field(
        default=8080,
        ge=1024,
        le=65535,
        description="API port",
    )

    # Security
    api_key: str | None = Field(
        default=None,
        description="API key for management endpoints (optional)",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
