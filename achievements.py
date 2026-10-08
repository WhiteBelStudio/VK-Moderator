from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AchievementSystem:
    ACHIEVEMENTS: dict[str, dict[str, Any]] = {
        "first_message": {
            "title": "Первое слово",
            "description": "Отправить первое сообщение",
            "icon": "💬",
            "type": "messages",
            "value": 1,
        },
        "messages_10": {
            "title": "Разговорился",
            "description": "Отправить 10 сообщений",
            "icon": "🗣",
            "type": "messages",
            "value": 10,
        },
        "messages_100": {
            "title": "Активист",
            "description": "Отправить 100 сообщений",
            "icon": "🔥",
            "type": "messages",
            "value": 100,
        },
        "messages_500": {
            "title": "Постоянный участник",
            "description": "Отправить 500 сообщений",
            "icon": "⭐",
            "type": "messages",
            "value": 500,
        },
        "messages_1000": {
            "title": "Легенда чата",
            "description": "Отправить 1000 сообщений",
            "icon": "👑",
            "type": "messages",
            "value": 1000,
        },
        "xp_100": {
            "title": "Первые очки",
            "description": "Получить 100 XP",
            "icon": "💎",
            "type": "xp",
            "value": 100,
        },
        "xp_500": {
            "title": "Опытный",
            "description": "Получить 500 XP",
            "icon": "💠",
            "type": "xp",
            "value": 500,
        },
        "xp_1000": {
            "title": "Мастер XP",
            "description": "Получить 1000 XP",
            "icon": "🏆",
            "type": "xp",
            "value": 1000,
        },
        "rp_10": {
            "title": "Общительный",
            "description": "Совершить 10 RP-действий",
            "icon": "🎭",
            "type": "rp",
            "value": 10,
        },
        "rp_50": {
            "title": "RP-мастер",
            "description": "Совершить 50 RP-действий",
            "icon": "🎬",
            "type": "rp",
            "value": 50,
        },
        "rp_100": {
            "title": "Главный актёр",
            "description": "Совершить 100 RP-действий",
            "icon": "🌟",
            "type": "rp",
            "value": 100,
        },
    }

    def __init__(
        self,
        db=None,
        db_path: str = "data/bot.db",
    ):
        self.db = db

        if db is not None:
            self.path = getattr(
                db,
                "path",
                db_path,
            )
        else:
            self.path = db_path

        Path(self.path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._create_tables()

    # ========================================================
    # DATABASE
    # ========================================================

    def connect(self):
        connection = sqlite3.connect(
            self.path,
            timeout=30,
        )

        connection.row_factory = sqlite3.Row

        connection.execute(
            "PRAGMA journal_mode=WAL"
        )

        return connection

    def _create_tables(self):
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS achievements (
                    achievement_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    icon TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_achievements (
                    user_id INTEGER NOT NULL,
                    achievement_id TEXT NOT NULL,
                    earned_at TEXT NOT NULL,

                    PRIMARY KEY (
                        user_id,
                        achievement_id
                    )
                );

                CREATE INDEX IF NOT EXISTS
                idx_user_achievements_user
                ON user_achievements(user_id);
                """
            )

            now = self.now()

            for achievement_id, achievement in self.ACHIEVEMENTS.items():
                db.execute(
                    """
                    INSERT OR IGNORE INTO achievements (
                        achievement_id,
                        title,
                        description,
                        icon,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        achievement_id,
                        achievement["title"],
                        achievement["description"],
                        achievement["icon"],
                        now,
                    ),
                )

    # ========================================================
    # TIME
    # ========================================================

    @staticmethod
    def now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    # ========================================================
    # CHECK USER
    # ========================================================

    def check_user(
        self,
        user_id: int,
        messages: int,
        xp: int,
        rp_count: int,
        level: int,
    ) -> list[dict[str, Any]]:

        values = {
            "messages": int(messages or 0),
            "xp": int(xp or 0),
            "rp": int(rp_count or 0),
            "level": int(level or 1),
        }

        earned = []

        for achievement_id, achievement in self.ACHIEVEMENTS.items():

            achievement_type = achievement["type"]

            current = values.get(
                achievement_type,
                0,
            )

            required = int(
                achievement["value"]
            )

            if current < required:
                continue

            if self.award(
                user_id,
                achievement_id,
            ):
                earned.append(
                    {
                        "id": achievement_id,
                        **achievement,
                    }
                )

        return earned

    # ========================================================
    # PROCESS MESSAGE
    # ========================================================

    def process_message(
        self,
        user_id: int,
    ) -> list[dict[str, Any]]:

        if self.db is None:
            return []

        user = self.db.get_user(
            user_id
        )

        if not user:
            return []

        return self.check_user(
            user_id=user_id,
            messages=user["messages"],
            xp=user["xp"],
            rp_count=user["rp_count"],
            level=user["level"],
        )

    # ========================================================
    # AWARD
    # ========================================================

    def award(
        self,
        user_id: int,
        achievement_id: str,
    ) -> bool:

        if achievement_id not in self.ACHIEVEMENTS:
            return False

        with self.connect() as db:
            cursor = db.execute(
                """
                INSERT OR IGNORE INTO user_achievements (
                    user_id,
                    achievement_id,
                    earned_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    user_id,
                    achievement_id,
                    self.now(),
                ),
            )

            return cursor.rowcount > 0

    # ========================================================
    # GET USER ACHIEVEMENTS
    # ========================================================

    def get_user_achievements(
        self,
        user_id: int,
    ):

        with self.connect() as db:
            return db.execute(
                """
                SELECT
                    a.achievement_id,
                    a.title,
                    a.description,
                    a.icon,
                    ua.earned_at
                FROM user_achievements ua
                JOIN achievements a
                    ON a.achievement_id = ua.achievement_id
                WHERE ua.user_id = ?
                ORDER BY ua.earned_at ASC
                """,
                (user_id,),
            ).fetchall()

    # ========================================================
    # COUNT
    # ========================================================

    def get_count(
        self,
        user_id: int,
    ) -> int:

        with self.connect() as db:
            row = db.execute(
                """
                SELECT COUNT(*)
                FROM user_achievements
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

            return int(row[0])

    def get_total_count(self) -> int:
        return len(
            self.ACHIEVEMENTS
        )

    # ========================================================
    # FORMAT NEW ACHIEVEMENTS
    # ========================================================

    def format_new_achievements(
        self,
        achievements: list[dict[str, Any]],
    ) -> str:

        if not achievements:
            return ""

        lines = [
            "🏆 НОВОЕ ДОСТИЖЕНИЕ!",
            "",
        ]

        for achievement in achievements:
            lines.append(
                f"{achievement['icon']} "
                f"{achievement['title']}"
            )

            lines.append(
                achievement["description"]
            )

            lines.append("")

        return "\n".join(lines).strip()

    # ========================================================
    # FORMAT ALL
    # ========================================================

    def format_achievements(
        self,
        user_id: int,
        first_name: str = "Пользователь",
    ) -> str:

        achievements = self.get_user_achievements(
            user_id
        )

        total = self.get_total_count()

        lines = [
            "🏆 ДОСТИЖЕНИЯ",
            "",
            f"👤 {first_name}",
            "",
            f"⭐ Получено: "
            f"{len(achievements)} / {total}",
        ]

        if not achievements:
            lines.extend(
                [
                    "",
                    "Пока достижений нет.",
                    "",
                    "💡 Общайтесь в чате и "
                    "участвуйте в его жизни!",
                ]
            )

            return "\n".join(lines)

        lines.extend(
            [
                "",
            ]
        )

        for achievement in achievements:
            lines.append(
                f"{achievement['icon']} "
                f"{achievement['title']}"
            )

            lines.append(
                f"   {achievement['description']}"
            )

            lines.append("")

        return "\n".join(lines).strip()

    # ========================================================
    # OLD COMPATIBILITY
    # ========================================================

    def build_text(
        self,
        user_id: int,
        first_name: str = "Пользователь",
    ) -> str:

        return self.format_achievements(
            user_id,
            first_name,
        )

    async def handle_command(
        self,
        peer_id: int,
        user_id: int,
        text: str,
        first_name: str = "Пользователь",
    ) -> bool:

        command = (
            text.strip()
            .split(maxsplit=1)[0]
            .casefold()
        )

        if command not in {
            "!достижения",
            "!ачивки",
            "!достижение",
            "!ачивы",
            "!achievements",
        }:
            return False

        await self._reply(
            peer_id,
            self.format_achievements(
                user_id,
                first_name,
            ),
        )

        return True

    async def _reply(
        self,
        peer_id: int,
        text: str,
    ):

        if self.db is not None:
            bot = getattr(
                self.db,
                "bot",
                None,
            )

            if bot and hasattr(bot, "reply"):
                await bot.reply(
                    peer_id,
                    text,
                )

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):
        pass