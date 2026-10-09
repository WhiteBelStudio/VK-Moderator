from __future__ import annotations

import sqlite3
import shutil
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from database import Database


def validate_database(path: str | Path) -> str:
    """Validate SQLite integrity and identify a supported VK-Moderator DB."""
    database_path = Path(path).expanduser().resolve()
    if not database_path.is_file():
        raise FileNotFoundError(database_path)

    try:
        with closing(sqlite3.connect(str(database_path), timeout=30)) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise ValueError(f"SQLite integrity check failed for {database_path}")

            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }

            if {"schema_migrations", "users"} <= tables:
                row = connection.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
                ).fetchone()
                version = int(row[0]) if row else 0
                if not 1 <= version <= Database.SCHEMA_VERSION:
                    raise ValueError(
                        f"Unsupported main database schema version: {version}"
                    )
                return "main"

            if {"marriages", "marriage_proposals"} <= tables:
                return "marriage"

    except sqlite3.Error as exc:
        raise ValueError(f"Not a readable SQLite database: {database_path}") from exc

    raise ValueError(f"Unrecognized VK-Moderator database: {database_path}")


def backup_sqlite(source: str | Path, destination: str | Path) -> Path:
    """Create a consistent backup of either supported application database."""
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    if source_path == destination_path:
        raise ValueError("Backup destination must differ from source.")
    validate_database(source_path)
    if destination_path.exists():
        raise FileExistsError(destination_path)

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(source_path), timeout=30)) as source_db, closing(
        sqlite3.connect(str(destination_path), timeout=30)
    ) as destination_db:
        source_db.backup(destination_db)

    return destination_path


def restore_sqlite(
    source: str | Path,
    destination: str | Path,
) -> Path | None:
    """Restore a validated backup and preserve the previous database first."""
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    if source_path == destination_path:
        raise ValueError("Restore source must differ from destination.")

    source_kind = validate_database(source_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    safety_copy: Path | None = None

    if destination_path.exists():
        try:
            destination_kind = validate_database(destination_path)
        except (OSError, ValueError, RuntimeError):
            destination_kind = None

        if destination_kind is not None and destination_kind != source_kind:
            raise ValueError(
                f"Cannot restore {source_kind} database over {destination_kind} database."
            )

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        safety_copy = destination_path.with_name(
            f"{destination_path.stem}.pre-restore-{stamp}{destination_path.suffix}"
        )
        if destination_kind is not None:
            backup_sqlite(destination_path, safety_copy)
        else:
            shutil.copy2(destination_path, safety_copy)
            for suffix in ("-wal", "-shm"):
                sidecar = Path(f"{destination_path}{suffix}")
                if sidecar.is_file():
                    shutil.copy2(sidecar, Path(f"{safety_copy}{suffix}"))

    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{destination_path}{suffix}")
        if sidecar.exists():
            sidecar.unlink()

    with closing(sqlite3.connect(str(source_path), timeout=30)) as source_db, closing(
        sqlite3.connect(str(destination_path), timeout=30)
    ) as destination_db:
        source_db.backup(destination_db)

    if source_kind == "main":
        Database(str(destination_path))
    else:
        from marriage import MarriageDatabase

        MarriageDatabase(db_path=destination_path)

    return safety_copy
