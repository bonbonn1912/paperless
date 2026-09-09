from __future__ import annotations

import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.models.base import utc_now
from app.models.user import UserSession


class BackupService:
    def create_backup(self, target_dir: Optional[Path] = None) -> Path:
        """
        Create a consistent backup using SQLite Online Backup API and copy of documents/.
        Returns path to the backup folder.
        """
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = target_dir or (settings.DATA_DIR / "backups" / f"backup_{now_str}")
        dest.mkdir(parents=True, exist_ok=True)

        db_dest = dest / "app.sqlite3"
        docs_dest = dest / "documents"

        # 1. SQLite Online Backup API for WAL consistency
        src_conn = sqlite3.connect(str(settings.database_path))
        dst_conn = sqlite3.connect(str(db_dest))
        try:
            with dst_conn:
                src_conn.backup(dst_conn, pages=100, sleep=0.01)
        finally:
            src_conn.close()
            dst_conn.close()

        # 2. Copy documents directory
        if settings.documents_dir.exists():
            shutil.copytree(str(settings.documents_dir), str(docs_dest), dirs_exist_ok=True)

        # 3. Write manifest
        manifest = {
            "created_at": utc_now().isoformat(),
            "version": "1.0",
            "app_version": "0.1.0",
        }
        with open(dest / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

        return dest

    def restore_backup(self, backup_dir: Path) -> None:
        """
        Restore database and documents from a backup directory.
        Revokes all active sessions for security.
        """
        if not backup_dir.exists():
            raise ValueError(f"Backup directory {backup_dir} does not exist.")

        src_db = backup_dir / "app.sqlite3"
        src_docs = backup_dir / "documents"

        if not src_db.exists():
            raise ValueError("Backup missing app.sqlite3 file.")

        # 1. Restore SQLite database via file copy / replace
        settings.database_dir.mkdir(parents=True, exist_ok=True)
        # Remove WAL and SHM if present
        for f in (settings.database_dir / "app.sqlite3-wal", settings.database_dir / "app.sqlite3-shm"):
            if f.exists():
                f.unlink(missing_ok=True)

        shutil.copy2(str(src_db), str(settings.database_path))

        # 2. Restore documents
        if src_docs.exists():
            settings.documents_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(str(src_docs), str(settings.documents_dir), dirs_exist_ok=True)

        # 3. Revoke all sessions in restored DB
        conn = sqlite3.connect(str(settings.database_path))
        try:
            conn.execute("UPDATE sessions SET revoked = 1;")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()


backup_service = BackupService()
