from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


class ChatStats:
    def __init__(self, db_path: str = "data/bot.db"):
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
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                text TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        self.db.commit()

    # ========================================================
    # MESSAGE
    # ========================================================

    def register_message(
        self,
        peer_id: int,
        user_id: int,
        text: str = "",
    ) -> None:

        self.db.execute(
            """
            INSERT INTO chat_messages (
                peer_id,
                user_id,
                text,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                peer_id,
                user_id,
                text,
                datetime.now().isoformat(),
            ),
        )

        self.db.commit()

    # ========================================================
    # REPORT
    # ========================================================

    def get_report(
        self,
        peer_id: int,
        period: str = "today",
    ) -> str:

        now = datetime.now()

        if period == "today":
            start = now.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            period_name = "сегодня"

        elif period == "week":
            start = now - timedelta(days=7)
            period_name = "за 7 дней"

        elif period == "month":
            start = now - timedelta(days=30)
            period_name = "за 30 дней"

        elif period == "year":
            start = now - timedelta(days=365)
            period_name = "за год"

        else:
            start = None
            period_name = "за всё время"

        if start is None:

            row = self.db.execute(
                """
                SELECT
                    COUNT(*) AS messages,
                    COUNT(DISTINCT user_id) AS users
                FROM chat_messages
                WHERE peer_id = ?
                """,
                (peer_id,),
            ).fetchone()

        else:

            row = self.db.execute(
                """
                SELECT
                    COUNT(*) AS messages,
                    COUNT(DISTINCT user_id) AS users
                FROM chat_messages
                WHERE peer_id = ?
                  AND created_at >= ?
                """,
                (
                    peer_id,
                    start.isoformat(),
                ),
            ).fetchone()

        messages = row["messages"]
        users = row["users"]

        return (
            "📊 СТАТИСТИКА ЧАТА\n\n"
            f"🕐 Период: {period_name}\n\n"
            f"💬 Сообщений: {messages}\n"
            f"👥 Активных пользователей: {users}"
        )

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self) -> None:
        if self.db:
            self.db.close()
            self.db = None


# Совместимость
ChatStatsSystem = ChatStats