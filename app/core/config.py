from __future__ import annotations

from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import List, Optional


# --- Konstanta Aplikasi ---
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100
MIN_PASSWORD_LENGTH: int = 8
API_KEY_MIN_LENGTH: int = 32


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application Settings
    APP_NAME: str = "FastAPI App"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development | staging | production

    # Database Settings
    DATABASE_URL: str = "sqlite:///./app.db"

    # Redis Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_PREFIX: str = "fastapi-cache"
    REDIS_DEFAULT_TTL: int = 300  # 5 minutes
    REDIS_ENABLE: bool = True

    # Security Settings
    SECRET_KEY: str = "your-super-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # API Key (minimal 32 karakter di production)
    API_KEY: str = "demo-api-key-12345"

    # CORS Settings — kosongkan untuk allow all (hanya di development)
    CORS_ORIGINS: List[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # Rate Limiting (requests per minute, 0 = disabled)
    RATE_LIMIT_PER_MINUTE: int = 60

    # Pagination Defaults
    DEFAULT_PAGE_SIZE: int = DEFAULT_PAGE_SIZE
    MAX_PAGE_SIZE: int = MAX_PAGE_SIZE

    # Email Settings
    MAIL_SERVER: str = "localhost"
    MAIL_PORT: int = 587
    MAIL_USERNAME: Optional[str] = None
    MAIL_PASSWORD: Optional[str] = None
    MAIL_FROM: str = "noreply@fastapi.app"
    MAIL_FROM_NAME: str = "FastAPI App"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    MAIL_VALIDATE_CERTS: bool = True
    MAIL_USE_CREDENTIALS: bool = True

    # File Upload Settings
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_IMAGE_TYPES: set = {"image/jpeg", "image/png", "image/gif", "image/webp"}

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True
    )

    @property
    def is_production(self) -> bool:
        """Cek apakah environment adalah production."""
        return self.ENVIRONMENT.lower() == "production"

    @property
    def effective_cors_origins(self) -> List[str]:
        """Return CORS origins yang aman berdasarkan environment."""
        if self.is_production and self.CORS_ORIGINS == ["*"]:
            # Fallback aman di production jika belum dikonfigurasi
            return []
        return self.CORS_ORIGINS


settings = Settings()
