from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


class JoinLeaveSystem:
    def __init__(
        self,
        db_path: str = "data/bot.db",
    ):
        Path(db_path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.db = sqlite3.connect(
            db_path,
            check_same_thread=False,
        )

        self.db.row_factory = sqlite3.Row

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS join_leave (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        self.db.commit()

    # ========================================================
    # JOIN
    # ========================================================

    def register_join(
        self,
        peer_id: int,
        user_id: int,
    ) -> None:

        self._register(
            peer_id,
            user_id,
            "join",
        )

    # ========================================================
    # LEAVE
    # ========================================================

    def register_leave(
        self,
        peer_id: int,
        user_id: int,
    ) -> None:

        self._register(
            peer_id,
            user_id,
            "leave",
        )

    # ========================================================
    # REGISTER
    # ========================================================

    def _register(
        self,
        peer_id: int,
        user_id: int,
        action: str,
    ) -> None:

        self.db.execute(
            """
            INSERT INTO join_leave (
                peer_id,
                user_id,
                action,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                peer_id,
                user_id,
                action,
                datetime.now().isoformat(),
            ),
        )

        self.db.commit()

    # ========================================================
    # WELCOME
    # ========================================================

    def welcome_text(
        self,
        user_id: int,
        first_name: str = "пользователь",
    ) -> str:

        return (
            f"👋 Добро пожаловать, "
            f"[id{user_id}|{first_name}]!"
        )

    # ========================================================
    # LEAVE TEXT
    # ========================================================

    def leave_text(
        self,
        user_id: int,
        first_name: str = "пользователь",
    ) -> str:

        return (
            f"👋 [id{user_id}|{first_name}] "
            "покинул чат."
        )

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self) -> None:

        if self.db:
            self.db.close()
            self.db = None