from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    DATA_DIR: Path = Path("/data")
    DATABASE_URL: str = ""
    SECRET_KEY: str = "paperless-local-secret-key-please-change-in-production"

    # Hardware & Job limits (Linux 4 cores, 6GB RAM profile)
    MAX_UPLOAD_MB: int = 100
    MAX_BATCH_FILES: int = 100
    UPLOAD_CONCURRENCY: int = 2
    STATUS_MAX_ITEMS: int = 500
    MAX_CAPTURE_PAGES: int = 100
    MAX_CAPTURE_TOTAL_MB: int = 1024
    MAX_ASSEMBLED_PDF_MB: int = 1024
    CAPTURE_DRAFT_TTL_DAYS: int = 7
    MAX_PDF_PAGES: int = 300
    MAX_IMAGE_PIXELS: int = 40_000_000
    HEAVY_JOB_CONCURRENCY: int = 1
    HEAVY_CPU_LIMIT: int = 2
    HEAVY_MEMORY_MB: int = 3072
    OCR_PAGE_TIMEOUT_SECONDS: int = 90
    OMP_THREAD_LIMIT: int = 2
    OCR_LANGUAGES: str = "deu+eng"
    OCR_DPI: int = 250

    # Session configuration
    SESSION_COOKIE_NAME: str = "paperless_session"
    SESSION_MAX_AGE_SECONDS: int = 86400 * 30  # 30 days
    SESSION_IDLE_TIMEOUT_SECONDS: int = 86400 * 7  # 7 days
    CSRF_HEADER_NAME: str = "X-CSRF-Token"

    # JSON map of username -> Argon2id password hash
    APP_USERS_JSON: str = Field(
        default='{"admin":"$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$RdescudvJCsgqlfreOJAcw"}'
    )

    @field_validator("DATA_DIR", mode="before")
    @classmethod
    def parse_data_dir(cls, v: Any) -> Path:
        if isinstance(v, str):
            p = Path(v).expanduser().resolve()
        elif isinstance(v, Path):
            p = v.expanduser().resolve()
        else:
            p = Path("/data")
        # Check if /data is root and unwritable (common on macOS outside docker)
        if str(p) == "/data":
            try:
                # Test write/access
                p.mkdir(parents=True, exist_ok=True)
            except OSError:
                p = (Path.cwd() / "data").resolve()
        return p

    @property
    def documents_dir(self) -> Path:
        return self.DATA_DIR / "documents"

    @property
    def derived_dir(self) -> Path:
        return self.DATA_DIR / "derived"

    @property
    def staging_dir(self) -> Path:
        return self.DATA_DIR / "staging"

    @property
    def database_dir(self) -> Path:
        return self.DATA_DIR / "database"

    @property
    def exports_dir(self) -> Path:
        return self.DATA_DIR / "exports"

    @property
    def database_path(self) -> Path:
        return self.database_dir / "app.sqlite3"

    @property
    def effective_db_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"sqlite:///{self.database_path.as_posix()}"

    def get_users(self) -> Dict[str, str]:
        """Parse APP_USERS_JSON into username -> argon2id hash dict."""
        try:
            users = json.loads(self.APP_USERS_JSON)
            if isinstance(users, dict):
                return {str(k): str(v) for k, v in users.items()}
            return {}
        except Exception:
            return {}

    def ensure_directories(self) -> None:
        """Ensure all required directories exist on disk."""
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.derived_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.database_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
