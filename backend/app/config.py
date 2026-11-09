from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    database_url: str = "mongodb://127.0.0.1:27017/shiftproof?replicaSet=rs0"
    frontend_url: str = "http://localhost:5173"
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    cookie_secure: bool = False
    session_hours: int = 12
    worker_session_hours: int = 8
    job_namespace: str = Field(default="", pattern=r"^[a-z0-9_-]{0,16}$")
    mail_mode: Literal["file", "smtp"] = "file"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False
    mail_from: str = "ShiftProof <noreply@shiftproof.local>"
    storage_mode: Literal["local", "s3"] = "local"
    storage_directory: Path = Path("./data/evidence")
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_key_prefix: str = ""
    aws_region: str = "ap-south-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    gnani_api_key: str = ""
    gnani_stt_model: str = "prisma-v3.0"
    gnani_tts_model: str = "timbre-v3.0"
    gnani_tts_voice: str = "Shivani"
    gnani_tts_speed: float = Field(default=1.0, ge=0.85, le=1.15)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    max_upload_bytes: int = 25 * 1024 * 1024
    malware_scanner: str = ""

    @model_validator(mode="after")
    def production_settings(self):
        if self.storage_mode == "s3" and not self.s3_bucket:
            raise ValueError("S3_BUCKET is required for S3 evidence storage")
        if self.s3_key_prefix and (
            self.s3_key_prefix.startswith("/") or ".." in self.s3_key_prefix.split("/")
        ):
            raise ValueError("S3_KEY_PREFIX must be a relative object prefix")
        if self.mail_mode == "smtp" and self.smtp_user and not self.smtp_password:
            raise ValueError("SMTP_PASSWORD is required when SMTP_USER is configured")
        if self.app_env == "production":
            if not self.cookie_secure or self.mail_mode != "smtp":
                raise ValueError("Production requires secure cookies and SMTP email delivery")
            if not self.database_url.startswith(("postgresql", "mongodb://", "mongodb+srv://")):
                raise ValueError("Production requires MongoDB or PostgreSQL")
            if not self.frontend_url.startswith("https://"):
                raise ValueError("Production requires an HTTPS frontend")
            if not self.allowed_origins or any(
                not origin.startswith("https://") or "*" in origin for origin in self.allowed_origins
            ):
                raise ValueError("Production requires explicit HTTPS origins")
            if self.smtp_user and not self.smtp_starttls:
                raise ValueError("Production SMTP credentials require STARTTLS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
