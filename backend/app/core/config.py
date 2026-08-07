"""Application configuration via environment variables."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "H-SmartLearn Platform"
    app_version: str = "1.7.3"
    debug: bool = True

    database_url: str = "sqlite+aiosqlite:///./smartlearn.db"
    database_url_sync: str = "sqlite:///./smartlearn.db"

    llm_provider: str = "disabled"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: str = ""
    storage_path: str = "./storage"
    upload_dir: str = "./uploads"
    max_revision_count: int = 2
    workflow_timeout_seconds: int = 300
    workflow_step_delay_seconds: float = 0.0
    admin_api_key: Optional[str] = None
    max_upload_bytes: int = 10 * 1024 * 1024
    cors_origins: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
