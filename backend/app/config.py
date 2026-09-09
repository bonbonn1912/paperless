import functools
import json
from pathlib import Path
from typing import Any, Dict
from argon2 import PasswordHasher
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


@functools.lru_cache(maxsize=8)
def _hash_plain_password(password: str) -> str:
    """Generate Argon2id password hash for plain password string."""
    ph = PasswordHasher()
    return ph.hash(password)


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

    # AI / Ollama LLM Classification configuration
    OLLAMA_ENABLED: bool = True
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3.5:2b-q4_K_M"
    OLLAMA_KEEP_ALIVE: str = "3m"
    OLLAMA_CONTEXT_WINDOW: int = 8192
    OLLAMA_TIMEOUT_SECONDS: int = 120

    # Session configuration
    SESSION_COOKIE_NAME: str = "paperless_session"
    SESSION_MAX_AGE_SECONDS: int = 86400 * 30  # 30 days
    SESSION_IDLE_TIMEOUT_SECONDS: int = 86400 * 7  # 7 days
    CSRF_HEADER_NAME: str = "X-CSRF-Token"

    # Default admin user credentials (plain password auto-hashed with Argon2id)
    ADMIN_USER: str = "admin"
    ADMIN_PASSWORD: str = ""

    # JSON map of username -> Argon2id password hash (optional / multi-user)
    APP_USERS_JSON: str = Field(
        default='{"admin":"$argon2id$v=19$m=65536,t=3,p=4$Fy29plb68Zwy7Mt7TySA6g$VFIgxAUKS2E24O28/A4gMJ8nUCWmof+o/xIYWiqPYq0"}'
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
                backend_dir = Path(__file__).resolve().parent.parent
                root_dir = backend_dir.parent
                if (backend_dir / "data" / "documents").exists():
                    p = backend_dir / "data"
                elif (root_dir / "data" / "documents").exists():
                    p = root_dir / "data"
                elif (backend_dir / "data").exists():
                    p = backend_dir / "data"
                else:
                    p = root_dir / "data"
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
            if self.DATABASE_URL.startswith("sqlite:////data") and not Path("/data").exists():
                return f"sqlite:///{self.database_path.as_posix()}"
            return self.DATABASE_URL
        return f"sqlite:///{self.database_path.as_posix()}"

    def get_users(self) -> Dict[str, str]:
        """Parse APP_USERS_JSON and/or ADMIN_PASSWORD into username -> argon2id hash dict."""
        users: Dict[str, str] = {}
        try:
            parsed = json.loads(self.APP_USERS_JSON)
            if isinstance(parsed, dict):
                users = {str(k): str(v).replace("$$", "$") for k, v in parsed.items()}
        except Exception:
            pass

        # If ADMIN_PASSWORD is set as a plain string, auto-generate Argon2id hash for ADMIN_USER
        if self.ADMIN_PASSWORD:
            users[self.ADMIN_USER] = _hash_plain_password(self.ADMIN_PASSWORD)

        return users

    def ensure_directories(self) -> None:
        """Ensure all required directories exist on disk."""
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.derived_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.database_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
