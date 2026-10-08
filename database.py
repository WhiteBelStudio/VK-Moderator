from __future__ import annotations

import os
import sqlite3


class Database:
    """Единая основная SQLite-база бота."""

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
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT NOT NULL DEFAULT '',
                    last_name TEXT NOT NULL DEFAULT '',
                    xp INTEGER NOT NULL DEFAULT 0,
                    rp INTEGER NOT NULL DEFAULT 0,
                    warnings INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_users_xp ON users(xp DESC);

                CREATE TABLE IF NOT EXISTS rp_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    amount INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_rp_actions_user ON rp_actions(user_id);
                CREATE INDEX IF NOT EXISTS idx_warnings_user ON warnings(user_id);
                """
            )

    def ensure_user(self, user_id: int, first_name: str = "", last_name: str = "") -> None:
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO users(user_id, first_name, last_name)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (int(user_id), str(first_name), str(last_name)),
            )

    def get_user(self, user_id: int) -> sqlite3.Row | None:
        with self.connect() as db:
            return db.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (int(user_id),),
            ).fetchone()

    def add_xp(self, user_id: int, amount: int) -> int:
        self.ensure_user(user_id)
        with self.connect() as db:
            db.execute(
                "UPDATE users SET xp = MAX(0, xp + ?), updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (int(amount), int(user_id)),
            )
            row = db.execute(
                "SELECT xp FROM users WHERE user_id = ?",
                (int(user_id),),
            ).fetchone()
            return int(row["xp"])

    def add_rp_action(self, user_id: int, action: str, amount: int) -> int:
        self.ensure_user(user_id)
        with self.connect() as db:
            db.execute(
                "UPDATE users SET rp = MAX(0, rp + ?), updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (int(amount), int(user_id)),
            )
            db.execute(
                "INSERT INTO rp_actions(user_id, action, amount) VALUES (?, ?, ?)",
                (int(user_id), str(action), int(amount)),
            )
            row = db.execute(
                "SELECT rp FROM users WHERE user_id = ?",
                (int(user_id),),
            ).fetchone()
            return int(row["rp"])

    def get_warning_count(self, user_id: int) -> int:
        with self.connect() as db:
            row = db.execute(
                "SELECT COUNT(*) AS count FROM warnings WHERE user_id = ?",
                (int(user_id),),
            ).fetchone()
            return int(row["count"])

    def add_warning(self, user_id: int, reason: str = "") -> int:
        self.ensure_user(user_id)
        with self.connect() as db:
            db.execute(
                "INSERT INTO warnings(user_id, reason) VALUES (?, ?)",
                (int(user_id), str(reason)),
            )
        return self.get_warning_count(user_id)

    def get_xp_top(self, limit: int = 10) -> list[sqlite3.Row]:
        limit = max(1, min(int(limit), 50))
        with self.connect() as db:
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
        with self._connect() as connection:
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
        with self._connect() as connection:
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
        with self._connect() as connection:
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
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM players WHERE user_id = ?",
                (int(user_id),),
            ).fetchone()

    def get_top(self, limit: int = 10) -> list[sqlite3.Row]:
        limit = max(1, min(int(limit), 50))
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM players WHERE games > 0 ORDER BY wins DESC, games DESC LIMIT ?",
                (limit,),
            ).fetchall()
