# Application settings and environment variable loading (Pydantic BaseSettings)

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional
import secrets


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Security Settings (Required - no defaults for secrets)
    secret_key: str
    access_token_expire_minutes: int = Field(default=15)
    refresh_token_expire_days: int = Field(default=30)

    # Database Settings (Required - no defaults for credentials)
    database_url: str

    # MinIO/S3 Settings (Required - no defaults for credentials)
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str

    # Redis Settings (Required - no defaults)
    redis_url: str

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()