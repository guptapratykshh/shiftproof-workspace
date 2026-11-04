from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    database_url: str = "sqlite:///./data/shiftproof.db"
    frontend_url: str = "http://localhost:5173"
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    cookie_secure: bool = False
    session_hours: int = 12
    worker_session_hours: int = 8
    mail_mode: Literal["file", "smtp"] = "file"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False
    mail_from: str = "ShiftProof <noreply@shiftproof.local>"
    storage_mode: str = "local"
    storage_directory: Path = Path("./data/evidence")
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    gnani_api_key: str = ""
    gnani_stt_model: str = "prisma-v3.0"
    gnani_tts_model: str = "timbre-v3.0"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    max_upload_bytes: int = 25 * 1024 * 1024
    malware_scanner: str = ""

    @model_validator(mode="after")
    def production_settings(self):
        if self.mail_mode == "smtp" and self.smtp_user and not self.smtp_password:
            raise ValueError("SMTP_PASSWORD is required when SMTP_USER is configured")
        if self.app_env == "production":
            if not self.cookie_secure or self.mail_mode != "smtp":
                raise ValueError("Production requires secure cookies and SMTP email delivery")
            if not self.database_url.startswith("postgresql"):
                raise ValueError("Production requires PostgreSQL")
            if not self.frontend_url.startswith("https://"):
                raise ValueError("Production requires an HTTPS frontend")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
