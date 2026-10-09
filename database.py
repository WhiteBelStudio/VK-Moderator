from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from contextlib import closing
from pathlib import Path


class Database:
    """Единая основная SQLite-база бота с версионируемыми миграциями."""

    SCHEMA_VERSION = 3

    @staticmethod
    def _positive_user_id(value: int) -> int:
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("user_id must be a positive integer") from exc
        if normalized <= 0:
            raise ValueError("user_id must be a positive integer")
        return normalized

    def _migration_path(self) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")

    def _apply_migrations(self, connection: sqlite3.Connection) -> None:
        connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
        migrations = sorted(Path(self._migration_path()).glob("*.sql"))
        for migration in migrations:
            try:
                version = int(migration.stem.split("_", 1)[0])
            except ValueError:
                continue
            if version in applied:
                continue
            connection.executescript(migration.read_text(encoding="utf-8"))
            connection.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
        current = connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]
        if current > self.SCHEMA_VERSION:
            raise RuntimeError(f"Database schema version {current} is newer than supported {self.SCHEMA_VERSION}.")

    def __init__(self, path: str | None = None) -> None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        self.path = path or os.path.join(data_dir, "bot.db")
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _connect(self) -> sqlite3.Connection:
        return self.connect()

    def _init_db(self) -> None:
        with closing(self.connect()) as db, db:
            self._apply_migrations(db)
            # Schema is created exclusively by numbered migrations.

    def ensure_user(self, user_id: int, first_name: str = "", last_name: str = "") -> None:
        with closing(self.connect()) as db, db:
            db.execute(
                """
                INSERT INTO users(user_id, first_name, last_name)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    first_name = CASE
                        WHEN excluded.first_name <> '' THEN excluded.first_name
                        ELSE users.first_name
                    END,
                    last_name = CASE
                        WHEN excluded.last_name <> '' THEN excluded.last_name
                        ELSE users.last_name
                    END,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (self._positive_user_id(user_id), str(first_name), str(last_name)),
            )

    def get_user(self, user_id: int) -> sqlite3.Row | None:
        with closing(self.connect()) as db, db:
            return db.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (self._positive_user_id(user_id),),
            ).fetchone()

    def update_xp(self, user_id: int, xp: int, level: int) -> None:
        """Persist XP and level calculated by XPSystem."""
        normalized_user_id = self._positive_user_id(user_id)
        normalized_xp = max(0, int(xp))
        normalized_level = max(1, int(level))

        self.ensure_user(normalized_user_id)
        with closing(self.connect()) as db, db:
            db.execute(
                """
                UPDATE users
                SET xp = ?, level = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (normalized_xp, normalized_level, normalized_user_id),
            )

    def add_xp(self, user_id: int, amount: int) -> int:
        self.ensure_user(user_id)
        with closing(self.connect()) as db, db:
            db.execute(
                "UPDATE users SET xp = MAX(0, xp + ?), updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (int(amount), self._positive_user_id(user_id)),
            )
            row = db.execute(
                "SELECT xp FROM users WHERE user_id = ?",
                (self._positive_user_id(user_id),),
            ).fetchone()
            return int(row["xp"])

    def add_rp_action(self, user_id: int, action: str, amount: int) -> int:
        self.ensure_user(user_id)
        with closing(self.connect()) as db, db:
            db.execute(
                "UPDATE users SET rp = MAX(0, rp + ?), updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (int(amount), self._positive_user_id(user_id)),
            )
            db.execute(
                "INSERT INTO rp_actions(user_id, action, amount) VALUES (?, ?, ?)",
                (self._positive_user_id(user_id), str(action), int(amount)),
            )
            row = db.execute(
                "SELECT rp FROM users WHERE user_id = ?",
                (self._positive_user_id(user_id),),
            ).fetchone()
            return int(row["rp"])

    def get_warning_count(self, user_id: int) -> int:
        with closing(self.connect()) as db, db:
            row = db.execute(
                "SELECT COUNT(*) AS count FROM warnings WHERE user_id = ?",
                (self._positive_user_id(user_id),),
            ).fetchone()
            return int(row["count"])

    def add_warning(self, user_id: int, reason: str = "") -> int:
        self.ensure_user(user_id)
        with closing(self.connect()) as db, db:
            db.execute(
                "INSERT INTO warnings(user_id, reason) VALUES (?, ?)",
                (self._positive_user_id(user_id), str(reason)),
            )
        return self.get_warning_count(user_id)

    def remove_warning(self, user_id: int) -> int:
        """Remove the newest warning for a user and return the remaining count."""
        with closing(self.connect()) as db, db:
            db.execute(
                """
                DELETE FROM warnings
                WHERE id = (
                    SELECT id FROM warnings
                    WHERE user_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                )
                """,
                (self._positive_user_id(user_id),),
            )
            row = db.execute(
                "SELECT COUNT(*) AS count FROM warnings WHERE user_id = ?",
                (self._positive_user_id(user_id),),
            ).fetchone()
            return int(row["count"])

    def set_role(self, user_id: int, role: str) -> None:
        normalized_role = str(role).strip().casefold()
        if normalized_role not in {"user", "moderator", "admin"}:
            raise ValueError("role must be user, moderator, or admin")
        with closing(self.connect()) as db, db:
            if normalized_role == "user":
                db.execute("DELETE FROM user_roles WHERE user_id = ?", (self._positive_user_id(user_id),))
            else:
                db.execute(
                    """
                    INSERT INTO user_roles(user_id, role, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        role = excluded.role,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (self._positive_user_id(user_id), normalized_role),
                )

    def get_role(self, user_id: int) -> str:
        with closing(self.connect()) as db, db:
            row = db.execute(
                "SELECT role FROM user_roles WHERE user_id = ?",
                (self._positive_user_id(user_id),),
            ).fetchone()
            return str(row["role"]) if row else "user"

    def set_mute(
        self,
        user_id: int,
        duration_minutes: int,
        reason: str,
        created_by: int,
    ) -> None:
        duration = int(duration_minutes)
        if not 1 <= duration <= 10_080:
            raise ValueError("mute duration must be between 1 and 10080 minutes")
        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=duration)
        ).isoformat(timespec="seconds")
        with closing(self.connect()) as db, db:
            db.execute(
                """
                INSERT INTO moderation_restrictions(
                    user_id, restriction_type, expires_at, reason, created_by
                )
                VALUES (?, 'mute', ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    restriction_type = 'mute',
                    expires_at = excluded.expires_at,
                    reason = excluded.reason,
                    created_by = excluded.created_by,
                    created_at = CURRENT_TIMESTAMP
                """,
                (self._positive_user_id(user_id), expires_at, str(reason), self._positive_user_id(created_by)),
            )

    def is_muted(self, user_id: int) -> bool:
        with closing(self.connect()) as db, db:
            row = db.execute(
                """
                SELECT expires_at FROM moderation_restrictions
                WHERE user_id = ? AND restriction_type = 'mute'
                """,
                (self._positive_user_id(user_id),),
            ).fetchone()
            if row is None:
                return False
            try:
                expires_at = datetime.fromisoformat(str(row["expires_at"]))
                active = expires_at > datetime.now(timezone.utc)
            except (TypeError, ValueError):
                active = False
            if not active:
                db.execute(
                    "DELETE FROM moderation_restrictions WHERE user_id = ?",
                    (self._positive_user_id(user_id),),
                )
            return active

    def remove_mute(self, user_id: int) -> bool:
        with closing(self.connect()) as db, db:
            cursor = db.execute(
                "DELETE FROM moderation_restrictions WHERE user_id = ? AND restriction_type = 'mute'",
                (self._positive_user_id(user_id),),
            )
            return cursor.rowcount > 0

    def log_moderation_action(
        self,
        actor_id: int,
        target_id: int,
        action: str,
        reason: str = "",
    ) -> None:
        with closing(self.connect()) as db, db:
            db.execute(
                """
                INSERT INTO moderation_actions(actor_id, target_id, action, reason)
                VALUES (?, ?, ?, ?)
                """,
                (self._positive_user_id(actor_id), self._positive_user_id(target_id), str(action), str(reason)),
            )

    def get_xp_top(self, limit: int = 10) -> list[sqlite3.Row]:
        limit = max(1, min(int(limit), 50))
        with closing(self.connect()) as db, db:
            return db.execute(
                "SELECT * FROM users WHERE xp > 0 ORDER BY xp DESC, user_id ASC LIMIT ?",
                (limit,),
            ).fetchall()


class ManiacDatabase:
    """Игровая БД маньяка; объединение будет отдельным архитектурным этапом."""

    def __init__(self, path: str | None = None) -> None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        self.path = path or os.path.join(data_dir, "maniac.db")
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS players (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT NOT NULL DEFAULT '',
                    games INTEGER NOT NULL DEFAULT 0,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    maniac_games INTEGER NOT NULL DEFAULT 0,
                    sheriff_games INTEGER NOT NULL DEFAULT 0,
                    doctor_games INTEGER NOT NULL DEFAULT 0,
                    civilian_games INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def ensure_player(self, user_id: int, first_name: str) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO players(user_id, first_name) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET first_name = excluded.first_name",
                (int(user_id), str(first_name)),
            )

    def record_game(self, user_id: int, first_name: str, role: str, won: bool) -> None:
        self.ensure_player(user_id, first_name)
        role_column = {
            "maniac": "maniac_games",
            "sheriff": "sheriff_games",
            "doctor": "doctor_games",
            "civilian": "civilian_games",
        }.get(role)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE players SET games = games + 1, wins = wins + ?, losses = losses + ? WHERE user_id = ?",
                (1 if won else 0, 0 if won else 1, int(user_id)),
            )
            if role_column:
                connection.execute(
                    f"UPDATE players SET {role_column} = {role_column} + 1 WHERE user_id = ?",
                    (int(user_id),),
                )

    def get_stats(self, user_id: int) -> sqlite3.Row | None:
        with closing(self._connect()) as connection, connection:
            return connection.execute(
                "SELECT * FROM players WHERE user_id = ?",
                (int(user_id),),
            ).fetchone()

    def get_top(self, limit: int = 10) -> list[sqlite3.Row]:
        limit = max(1, min(int(limit), 50))
        with closing(self._connect()) as connection, connection:
            return connection.execute(
                "SELECT * FROM players WHERE games > 0 ORDER BY wins DESC, games DESC LIMIT ?",
                (limit,),
            ).fetchall()
