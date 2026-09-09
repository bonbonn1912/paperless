from __future__ import annotations

import sqlite3
from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.config import settings

Base = declarative_base()


def _set_sqlite_pragmas(dbapi_connection: sqlite3.Connection, connection_record: object) -> None:
    """Apply performance, concurrency, and integrity pragmas for SQLite WAL."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA busy_timeout = 30000;")  # 30s wait on locks
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.close()


def create_db_engine(db_url: str | None = None) -> Engine:
    url = db_url or settings.effective_db_url
    # Ensure directory exists if using local file path
    if url.startswith("sqlite:////"):
        file_path = url[len("sqlite:///"):]
        from pathlib import Path
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    elif url.startswith("sqlite:///"):
        file_path = url[len("sqlite:///"):]
        if file_path and not file_path.startswith(":memory:"):
            from pathlib import Path
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db(engine_instance: Engine | None = None) -> None:
    """Initialize relational models and FTS5 search index."""
    eng = engine_instance or engine
    Base.metadata.create_all(bind=eng)

    # Initialize FTS5 search table and ensure columns exist
    with eng.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE documents ADD COLUMN search_keywords TEXT"))
        except Exception:
            pass

        conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS search_documents USING fts5(
                    document_id UNINDEXED,
                    owner UNINDEXED,
                    content,
                    title,
                    original_name,
                    sender,
                    tag_names,
                    tokenize = 'unicode61'
                );
                """
            )
        )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
