"""Application configuration using Pydantic Settings."""

import os
from functools import lru_cache
from typing import List, Optional, Union
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "ConvoMind API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str = (
        "postgresql+asyncpg://convo_user:convo_password@postgres:5432/convo_db"
    )

    REDIS_URL: str = "redis://redis:6379/0"

    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    CORS_ORIGINS: Union[str, List[str]] = ["http://localhost:5173"]

    JWT_SECRET_KEY: str = "change-this-in-development"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    STORAGE_BACKEND: str = "local"
    STORAGE_PATH: str = os.getenv(
        "STORAGE_PATH",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage")),
    )
    MAX_UPLOAD_SIZE_MB: int = 500

    TRANSCRIPTION_PROVIDER: str = "whisper"
    OPENAI_API_KEY: Optional[str] = None
    WHISPER_MODEL: str = "whisper-1"

    LLM_PROVIDER: str = "mock"
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 4096
    LLM_TIMEOUT_SECONDS: int = 90
    MAX_TRANSCRIPT_TOKENS: int = 100000

    EMBEDDING_PROVIDER: str = "mock"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    EMBEDDING_CHUNK_SIZE: int = 500
    EMBEDDING_CHUNK_OVERLAP: int = 100
    EMBEDDING_BATCH_SIZE: int = 50

    DIARIZATION_PROVIDER: str = "mock"
    DIARIZATION_MODEL: str = "pyannote/speaker-diarization-3.1"
    DIARIZATION_HF_TOKEN: Optional[str] = None
    DIARIZATION_TIMEOUT: int = 300
    DIARIZATION_MAX_DURATION: int = 14400

    APP_BASE_URL: str = "http://localhost:5173"

    EMAIL_PROVIDER: str = "mock"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "noreply@convomind.ai"
    SMTP_FROM_NAME: str = "ConvoMind"
    SMTP_USE_TLS: bool = False

    MEDIA_PROVIDER: str = "mock"
    LIVEKIT_URL: Optional[str] = None
    LIVEKIT_API_KEY: Optional[str] = None
    LIVEKIT_API_SECRET: Optional[str] = None

    RAZORPAY_KEY_ID: str = "rzp_test_placeholder"
    RAZORPAY_KEY_SECRET: str = "placeholder_secret"
    RAZORPAY_WEBHOOK_SECRET: str = "placeholder_webhook_secret"


    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS_ORIGINS normalized as a list of strings."""
        if isinstance(self.CORS_ORIGINS, str):
            return [
                origin.strip()
                for origin in self.CORS_ORIGINS.split(",")
                if origin.strip()
            ]
        return list(self.CORS_ORIGINS)


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()


settings = get_settings()
