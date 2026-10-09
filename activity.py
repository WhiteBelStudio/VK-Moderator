from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


class ActivitySystem:
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
            CREATE TABLE IF NOT EXISTS user_activity (
                user_id INTEGER PRIMARY KEY,
                messages INTEGER NOT NULL DEFAULT 0,
                last_message TEXT NOT NULL
            )
            """
        )

        self.db.commit()

    # ========================================================
    # REGISTER
    # ========================================================

    def register_message(
        self,
        user_id: int,
    ) -> None:

        now = datetime.now().isoformat()

        self.db.execute(
            """
            INSERT INTO user_activity (
                user_id,
                messages,
                last_message
            )
            VALUES (?, 1, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                messages = messages + 1,
                last_message = excluded.last_message
            """,
            (
                user_id,
                now,
            ),
        )

        self.db.commit()

    # ========================================================
    # GET ACTIVITY
    # ========================================================

    def get_activity(
        self,
        user_id: int,
    ) -> dict:

        row = self.db.execute(
            """
            SELECT
                user_id,
                messages,
                last_message
            FROM user_activity
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if not row:
            return {
                "user_id": user_id,
                "messages": 0,
                "last_message": None,
            }

        return {
            "user_id": row["user_id"],
            "messages": row["messages"],
            "last_message": row["last_message"],
        }

    # ========================================================
    # REPORT
    # ========================================================

    def get_report(
        self,
        user_id: int,
    ) -> str:

        activity = self.get_activity(
            user_id
        )

        return (
            "📊 АКТИВНОСТЬ\n\n"
            f"💬 Сообщений: "
            f"{activity['messages']}\n"
            f"🕐 Последнее сообщение: "
            f"{activity['last_message'] or 'нет'}"
        )

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self) -> None:

        if self.db:
            self.db.close()
            self.db = None


# Совместимость
ActivitySystem = ActivitySystem