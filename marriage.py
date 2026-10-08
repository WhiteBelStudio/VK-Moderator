from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


# ============================================================
# DATABASE
# ============================================================

class MarriageDatabase:
    """
    Отдельная БД системы игровых браков.

    Файл:
        marriage/data/marriage.db
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
    ):
        if db_path is None:
            db_path = (
                Path(__file__).resolve().parent
                / "data"
                / "marriage.db"
            )

        self.db_path = Path(db_path)

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            timeout=30,
        )

        conn.row_factory = sqlite3.Row

        conn.execute(
            "PRAGMA foreign_keys = ON"
        )

        conn.execute(
            "PRAGMA journal_mode = WAL"
        )

        conn.execute(
            "PRAGMA busy_timeout = 30000"
        )

        return conn

    def init_db(self) -> None:
        with self.connect() as db:

            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS marriages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user1_id INTEGER NOT NULL,
                    user2_id INTEGER NOT NULL,

                    married_at TEXT NOT NULL,

                    active INTEGER NOT NULL DEFAULT 1,

                    divorced_at TEXT DEFAULT NULL,

                    CHECK (user1_id != user2_id)
                );

                CREATE TABLE IF NOT EXISTS marriage_proposals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    from_user_id INTEGER NOT NULL,
                    to_user_id INTEGER NOT NULL,

                    created_at TEXT NOT NULL,

                    status TEXT NOT NULL DEFAULT 'pending',

                    processed_at TEXT DEFAULT NULL,

                    CHECK (from_user_id != to_user_id),

                    CHECK (
                        status IN (
                            'pending',
                            'accepted',
                            'declined',
                            'cancelled'
                        )
                    )
                );

                CREATE INDEX IF NOT EXISTS idx_marriages_user1
                ON marriages(user1_id);

                CREATE INDEX IF NOT EXISTS idx_marriages_user2
                ON marriages(user2_id);

                CREATE INDEX IF NOT EXISTS idx_marriages_active
                ON marriages(active);

                CREATE INDEX IF NOT EXISTS idx_marriages_dates
                ON marriages(married_at, divorced_at);

                CREATE INDEX IF NOT EXISTS idx_proposals_to_status
                ON marriage_proposals(
                    to_user_id,
                    status
                );

                CREATE INDEX IF NOT EXISTS idx_proposals_from_status
                ON marriage_proposals(
                    from_user_id,
                    status
                );

                CREATE INDEX IF NOT EXISTS idx_proposals_pair
                ON marriage_proposals(
                    from_user_id,
                    to_user_id,
                    status
                );
                """
            )

    @staticmethod
    def now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    # ========================================================
    # MARRIAGE
    # ========================================================

    def get_marriage(
        self,
        user_id: int,
    ) -> sqlite3.Row | None:

        user_id = int(user_id)

        with self.connect() as db:

            return db.execute(
                """
                SELECT *
                FROM marriages
                WHERE active = 1
                  AND (
                      user1_id = ?
                      OR user2_id = ?
                  )
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    user_id,
                    user_id,
                ),
            ).fetchone()

    def get_marriage_by_id(
        self,
        marriage_id: int,
    ) -> sqlite3.Row | None:

        with self.connect() as db:

            return db.execute(
                """
                SELECT *
                FROM marriages
                WHERE id = ?
                LIMIT 1
                """,
                (
                    int(marriage_id),
                ),
            ).fetchone()

    def create_marriage(
        self,
        user1_id: int,
        user2_id: int,
    ) -> int:

        user1_id = int(user1_id)
        user2_id = int(user2_id)

        if user1_id == user2_id:

            raise ValueError(
                "Нельзя заключить брак с самим собой."
            )

        if self.get_marriage(user1_id):

            raise ValueError(
                "У первого пользователя уже есть активный брак."
            )

        if self.get_marriage(user2_id):

            raise ValueError(
                "У второго пользователя уже есть активный брак."
            )

        first_id = min(
            user1_id,
            user2_id,
        )

        second_id = max(
            user1_id,
            user2_id,
        )

        with self.connect() as db:

            cursor = db.execute(
                """
                INSERT INTO marriages (
                    user1_id,
                    user2_id,
                    married_at,
                    active
                )
                VALUES (?, ?, ?, 1)
                """,
                (
                    first_id,
                    second_id,
                    self.now(),
                ),
            )

            return int(
                cursor.lastrowid
            )

    def divorce(
        self,
        user_id: int,
    ) -> sqlite3.Row | None:

        marriage = self.get_marriage(
            user_id
        )

        if not marriage:
            return None

        marriage_id = int(
            marriage["id"]
        )

        divorced_at = self.now()

        with self.connect() as db:

            db.execute(
                """
                UPDATE marriages
                SET active = 0,
                    divorced_at = ?
                WHERE id = ?
                  AND active = 1
                """,
                (
                    divorced_at,
                    marriage_id,
                ),
            )

            return db.execute(
                """
                SELECT *
                FROM marriages
                WHERE id = ?
                LIMIT 1
                """,
                (
                    marriage_id,
                ),
            ).fetchone()

    # ========================================================
    # PROPOSALS
    # ========================================================

    def get_pending_proposal_to(
        self,
        user_id: int,
    ) -> sqlite3.Row | None:

        with self.connect() as db:

            return db.execute(
                """
                SELECT *
                FROM marriage_proposals
                WHERE to_user_id = ?
                  AND status = 'pending'
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    int(user_id),
                ),
            ).fetchone()

    def get_pending_proposal_from(
        self,
        user_id: int,
    ) -> sqlite3.Row | None:

        with self.connect() as db:

            return db.execute(
                """
                SELECT *
                FROM marriage_proposals
                WHERE from_user_id = ?
                  AND status = 'pending'
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    int(user_id),
                ),
            ).fetchone()

    def get_pending_count(self) -> int:

        with self.connect() as db:

            row = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM marriage_proposals
                WHERE status = 'pending'
                """
            ).fetchone()

            return int(
                row["count"]
            )

    def create_proposal(
        self,
        from_user_id: int,
        to_user_id: int,
    ) -> int:

        from_user_id = int(
            from_user_id
        )

        to_user_id = int(
            to_user_id
        )

        if from_user_id == to_user_id:

            raise ValueError(
                "Нельзя отправить предложение самому себе."
            )

        if self.get_marriage(
            from_user_id
        ):

            raise ValueError(
                "У тебя уже есть активный брак."
            )

        if self.get_marriage(
            to_user_id
        ):

            raise ValueError(
                "У пользователя уже есть активный брак."
            )

        if self.get_pending_proposal_from(
            from_user_id
        ):

            raise ValueError(
                "У тебя уже есть активное предложение."
            )

        with self.connect() as db:

            existing = db.execute(
                """
                SELECT id
                FROM marriage_proposals
                WHERE status = 'pending'
                  AND (
                      (
                          from_user_id = ?
                          AND to_user_id = ?
                      )
                      OR
                      (
                          from_user_id = ?
                          AND to_user_id = ?
                      )
                  )
                LIMIT 1
                """,
                (
                    from_user_id,
                    to_user_id,
                    to_user_id,
                    from_user_id,
                ),
            ).fetchone()

            if existing:

                raise ValueError(
                    "Между этими пользователями уже есть активное предложение."
                )

            cursor = db.execute(
                """
                INSERT INTO marriage_proposals (
                    from_user_id,
                    to_user_id,
                    created_at,
                    status
                )
                VALUES (?, ?, ?, 'pending')
                """,
                (
                    from_user_id,
                    to_user_id,
                    self.now(),
                ),
            )

            return int(
                cursor.lastrowid
            )

    def accept_proposal(
        self,
        proposal_id: int,
        user_id: int,
    ) -> sqlite3.Row | None:

        proposal_id = int(
            proposal_id
        )

        user_id = int(
            user_id
        )

        with self.connect() as db:

            proposal = db.execute(
                """
                SELECT *
                FROM marriage_proposals
                WHERE id = ?
                  AND to_user_id = ?
                  AND status = 'pending'
                LIMIT 1
                """,
                (
                    proposal_id,
                    user_id,
                ),
            ).fetchone()

            if not proposal:
                return None

            from_user_id = int(
                proposal["from_user_id"]
            )

            to_user_id = int(
                proposal["to_user_id"]
            )

            existing = db.execute(
                """
                SELECT id
                FROM marriages
                WHERE active = 1
                  AND (
                      user1_id IN (?, ?)
                      OR user2_id IN (?, ?)
                  )
                LIMIT 1
                """,
                (
                    from_user_id,
                    to_user_id,
                    from_user_id,
                    to_user_id,
                ),
            ).fetchone()

            if existing:
                return None

            first_id = min(
                from_user_id,
                to_user_id,
            )

            second_id = max(
                from_user_id,
                to_user_id,
            )

            now = self.now()

            cursor = db.execute(
                """
                INSERT INTO marriages (
                    user1_id,
                    user2_id,
                    married_at,
                    active
                )
                VALUES (?, ?, ?, 1)
                """,
                (
                    first_id,
                    second_id,
                    now,
                ),
            )

            marriage_id = int(
                cursor.lastrowid
            )

            db.execute(
                """
                UPDATE marriage_proposals
                SET status = 'accepted',
                    processed_at = ?
                WHERE id = ?
                """,
                (
                    now,
                    proposal_id,
                ),
            )

            db.execute(
                """
                UPDATE marriage_proposals
                SET status = 'cancelled',
                    processed_at = ?
                WHERE status = 'pending'
                  AND id != ?
                  AND (
                      from_user_id IN (?, ?)
                      OR to_user_id IN (?, ?)
                  )
                """,
                (
                    now,
                    proposal_id,
                    from_user_id,
                    to_user_id,
                    from_user_id,
                    to_user_id,
                ),
            )

            return db.execute(
                """
                SELECT *
                FROM marriages
                WHERE id = ?
                LIMIT 1
                """,
                (
                    marriage_id,
                ),
            ).fetchone()

    def decline_proposal(
        self,
        proposal_id: int,
        user_id: int,
    ) -> sqlite3.Row | None:

        with self.connect() as db:

            proposal = db.execute(
                """
                SELECT *
                FROM marriage_proposals
                WHERE id = ?
                  AND to_user_id = ?
                  AND status = 'pending'
                LIMIT 1
                """,
                (
                    int(proposal_id),
                    int(user_id),
                ),
            ).fetchone()

            if not proposal:
                return None

            db.execute(
                """
                UPDATE marriage_proposals
                SET status = 'declined',
                    processed_at = ?
                WHERE id = ?
                  AND status = 'pending'
                """,
                (
                    self.now(),
                    int(proposal_id),
                ),
            )

            return proposal

    def cancel_proposal(
        self,
        proposal_id: int,
        user_id: int,
    ) -> sqlite3.Row | None:

        with self.connect() as db:

            proposal = db.execute(
                """
                SELECT *
                FROM marriage_proposals
                WHERE id = ?
                  AND from_user_id = ?
                  AND status = 'pending'
                LIMIT 1
                """,
                (
                    int(proposal_id),
                    int(user_id),
                ),
            ).fetchone()

            if not proposal:
                return None

            db.execute(
                """
                UPDATE marriage_proposals
                SET status = 'cancelled',
                    processed_at = ?
                WHERE id = ?
                  AND status = 'pending'
                """,
                (
                    self.now(),
                    int(proposal_id),
                ),
            )

            return proposal

    # ========================================================
    # STATISTICS
    # ========================================================

    def get_statistics(
        self,
    ) -> dict[str, int]:

        with self.connect() as db:

            total = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM marriages
                """
            ).fetchone()["count"]

            active = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM marriages
                WHERE active = 1
                """
            ).fetchone()["count"]

            divorced = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM marriages
                WHERE active = 0
                  AND divorced_at IS NOT NULL
                """
            ).fetchone()["count"]

            proposals_total = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM marriage_proposals
                """
            ).fetchone()["count"]

            proposals_accepted = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM marriage_proposals
                WHERE status = 'accepted'
                """
            ).fetchone()["count"]

            proposals_declined = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM marriage_proposals
                WHERE status = 'declined'
                """
            ).fetchone()["count"]

            proposals_cancelled = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM marriage_proposals
                WHERE status = 'cancelled'
                """
            ).fetchone()["count"]

            pending = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM marriage_proposals
                WHERE status = 'pending'
                """
            ).fetchone()["count"]

            return {
                "total_marriages": int(total),
                "active_marriages": int(active),
                "divorced_marriages": int(divorced),
                "proposals_total": int(
                    proposals_total
                ),
                "proposals_accepted": int(
                    proposals_accepted
                ),
                "proposals_declined": int(
                    proposals_declined
                ),
                "proposals_cancelled": int(
                    proposals_cancelled
                ),
                "pending_proposals": int(
                    pending
                ),
            }

    # ========================================================
    # TOP COUPLES
    # ========================================================

    def get_top_couples(
        self,
        limit: int = 10,
    ) -> list[sqlite3.Row]:

        limit = max(
            1,
            min(
                int(limit),
                100,
            ),
        )

        with self.connect() as db:

            return db.execute(
                """
                SELECT
                    id,
                    user1_id,
                    user2_id,
                    married_at,
                    active,
                    divorced_at
                FROM marriages
                WHERE active = 1
                ORDER BY
                    married_at ASC,
                    id ASC
                LIMIT ?
                """,
                (
                    limit,
                ),
            ).fetchall()

    # ========================================================
    # HISTORY
    # ========================================================

    def get_history(
        self,
        user_id: int,
        limit: int = 20,
    ) -> list[sqlite3.Row]:

        limit = max(
            1,
            min(
                int(limit),
                100,
            ),
        )

        with self.connect() as db:

            return db.execute(
                """
                SELECT *
                FROM marriages
                WHERE user1_id = ?
                   OR user2_id = ?
                ORDER BY
                    married_at DESC,
                    id DESC
                LIMIT ?
                """,
                (
                    int(user_id),
                    int(user_id),
                    limit,
                ),
            ).fetchall()

    def get_all_history(
        self,
        limit: int = 100,
    ) -> list[sqlite3.Row]:

        limit = max(
            1,
            min(
                int(limit),
                500,
            ),
        )

        with self.connect() as db:

            return db.execute(
                """
                SELECT *
                FROM marriages
                ORDER BY
                    married_at DESC,
                    id DESC
                LIMIT ?
                """,
                (
                    limit,
                ),
            ).fetchall()


# ============================================================
# MARRIAGE MODULE
# ============================================================

class MarriageModule:

    COMMANDS = {
        "!брак",
        "!принять",
        "!отказать",
        "!отменить",
        "!развод",
        "!пара",
        "!топпар",
        "!статбрак",
        "!историябрака",
        "!бракпомощь",
    }

    def __init__(
        self,
        vk: Any,
        core_db: Any | None = None,
        db_path: str | Path | None = None,
    ):
        self.vk = vk
        self.core_db = core_db

        self.db = MarriageDatabase(
            db_path=db_path
        )

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def clean_name(
        name: str | None,
        fallback: str = "Пользователь",
    ) -> str:

        name = str(
            name or ""
        ).strip()

        return (
            name
            or fallback
        )

    @classmethod
    def mention(
        cls,
        user_id: int,
        name: str | None = None,
    ) -> str:

        safe_name = cls.clean_name(
            name,
            f"ID {user_id}",
        )

        safe_name = escape(
            safe_name
        )

        return (
            f"[id{int(user_id)}|"
            f"{safe_name}]"
        )

    @staticmethod
    def parse_user_id(
        text: str,
    ) -> int | None:

        text = (
            text
            or ""
        ).strip()

        if not text:
            return None

        patterns = (
            # VK native mention:
            # [id651547667|Вадим]
            r"\[id(\d+)\|",

            # VK group mention:
            # [club123|Название]
            r"\[club(\d+)\|",

            # Markdown VK link:
            # [Вадим](https://vk.ru/id651547667)
            r"\]\(\s*https?://(?:www\.)?vk\.ru/id(\d+)\s*\)",

            # Markdown VK link:
            # [Вадим](https://vk.com/id651547667)
            r"\]\(\s*https?://(?:www\.)?vk\.com/id(\d+)\s*\)",

            # Direct vk.ru link
            r"https?://(?:www\.)?vk\.ru/id(\d+)",

            # Direct vk.com link
            r"https?://(?:www\.)?vk\.com/id(\d+)",

            # @id123
            r"@id(\d+)",

            # id123
            r"\bid(\d+)\b",

            # Just numeric ID
            r"(?<!\d)(\d{5,})(?!\d)",
        )

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:

                try:

                    return int(
                        match.group(1)
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    return None

        return None

    @staticmethod
    def parse_command(
        text: str,
    ) -> tuple[str, str]:

        text = (
            text
            or ""
        ).strip()

        if not text:
            return "", ""

        parts = text.split(
            maxsplit=1
        )

        command = (
            parts[0]
            .lower()
            .strip()
        )

        args = ""

        if len(parts) > 1:

            args = parts[1].strip()

        return (
            command,
            args,
        )

    @staticmethod
    def days_between(
        start: str,
        end: str | None = None,
    ) -> int:

        try:

            start_dt = datetime.fromisoformat(
                start
            )

            if start_dt.tzinfo is None:

                start_dt = start_dt.replace(
                    tzinfo=timezone.utc
                )

            if end:

                end_dt = datetime.fromisoformat(
                    end
                )

                if end_dt.tzinfo is None:

                    end_dt = end_dt.replace(
                        tzinfo=timezone.utc
                    )

            else:

                end_dt = datetime.now(
                    timezone.utc
                )

            return max(
                0,
                (
                    end_dt - start_dt
                ).days,
            )

        except (TypeError, ValueError, OverflowError, sqlite3.Error):

            logger.exception("Failed to calculate marriage duration.")
            return 0

    @staticmethod
    def format_date(
        value: str | None,
    ) -> str:

        if not value:
            return "неизвестно"

        try:

            dt = datetime.fromisoformat(
                value
            )

            if dt.tzinfo is None:

                dt = dt.replace(
                    tzinfo=timezone.utc
                )

            return dt.astimezone(
                timezone.utc
            ).strftime(
                "%d.%m.%Y"
            )

        except (TypeError, ValueError, OverflowError):

            logger.exception("Failed to format marriage date.")
            return "неизвестно"

    @staticmethod
    def plural(
        number: int,
        one: str,
        few: str,
        many: str,
    ) -> str:

        number = abs(
            int(number)
        )

        if (
            number % 10 == 1
            and number % 100 != 11
        ):
            return one

        if (
            number % 10 in (2, 3, 4)
            and number % 100 not in (
                12,
                13,
                14,
            )
        ):
            return few

        return many

    # ========================================================
    # VK USER
    # ========================================================

    async def get_vk_user(
        self,
        user_id: int,
    ) -> dict[str, Any]:

        try:

            result = await self.vk.call(
                "users.get",
                user_ids=str(
                    int(user_id)
                ),
                fields=(
                    "first_name,"
                    "last_name,"
                    "screen_name"
                ),
            )

            if (
                isinstance(result, list)
                and result
                and isinstance(result[0], dict)
            ):

                return result[0]

        except (VKAPIError, sqlite3.Error, TypeError, ValueError, KeyError):

            logger.exception("Optional marriage operation failed.")

        return {
            "id": int(user_id),
            "first_name": f"ID {user_id}",
            "last_name": "",
            "screen_name": "",
        }

    async def user_name(
        self,
        user_id: int,
    ) -> str:

        user_id = int(
            user_id
        )

        if self.core_db is not None:

            try:

                user = self.core_db.get_user(
                    user_id
                )

                if user:

                    first_name = (
                        user["first_name"]
                        or ""
                    )

                    last_name = (
                        user["last_name"]
                        or ""
                    )

                    name = (
                        f"{first_name} "
                        f"{last_name}"
                    ).strip()

                    if name:

                        return name

            except Exception:

                pass

        user = await self.get_vk_user(
            user_id
        )

        first_name = (
            user.get(
                "first_name"
            )
            or ""
        )

        last_name = (
            user.get(
                "last_name"
            )
            or ""
        )

        name = (
            f"{first_name} "
            f"{last_name}"
        ).strip()

        return (
            name
            or f"ID {user_id}"
        )

    # ========================================================
    # XP
    # ========================================================

    def get_user_xp(
        self,
        user_id: int,
    ) -> int:

        if self.core_db is None:
            return 0

        try:

            user = self.core_db.get_user(
                int(user_id)
            )

            if not user:
                return 0

            return int(
                user["xp"] or 0
            )

        except (TypeError, ValueError, OverflowError, sqlite3.Error):

            logger.exception("Failed to calculate marriage duration.")
            return 0

    def get_pair_xp(
        self,
        user1_id: int,
        user2_id: int,
    ) -> tuple[int, int, int]:

        xp1 = self.get_user_xp(
            user1_id
        )

        xp2 = self.get_user_xp(
            user2_id
        )

        return (
            xp1,
            xp2,
            xp1 + xp2,
        )

    # ========================================================
    # !БРАК
    # ========================================================

    async def command_marriage(
        self,
        peer_id: int,
        user_id: int,
        args: str,
    ) -> bool:

        if not args:

            await self.send(
                peer_id,
                await self.marriage_text(
                    user_id
                ),
            )

            return True

        target_id = self.parse_user_id(
            args
        )

        if target_id is None:

            await self.send(
                peer_id,
                (
                    "❌ Не удалось определить пользователя.\n\n"
                    "Использование:\n"
                    "!брак [id123]"
                ),
            )

            return True

        target_id = int(
            target_id
        )

        if target_id == int(user_id):

            await self.send(
                peer_id,
                "❌ Нельзя заключить брак с самим собой.",
            )

            return True

        current_marriage = (
            self.db.get_marriage(
                user_id
            )
        )

        if current_marriage:

            await self.send(
                peer_id,
                (
                    "❌ У тебя уже есть активный брак.\n\n"
                    "Используй !пара, чтобы посмотреть "
                    "своего партнёра."
                ),
            )

            return True

        target_marriage = (
            self.db.get_marriage(
                target_id
            )
        )

        if target_marriage:

            target_name = (
                await self.user_name(
                    target_id
                )
            )

            await self.send(
                peer_id,
                (
                    "❌ У "
                    f"{self.mention(target_id, target_name)} "
                    "уже есть активный брак."
                ),
            )

            return True

        outgoing = (
            self.db.get_pending_proposal_from(
                user_id
            )
        )

        if outgoing:

            await self.send(
                peer_id,
                (
                    "📨 У тебя уже есть активное "
                    "предложение.\n\n"
                    "Используй !отменить, "
                    "чтобы отменить его."
                ),
            )

            return True

        try:

            proposal_id = (
                self.db.create_proposal(
                    from_user_id=user_id,
                    to_user_id=target_id,
                )
            )

        except ValueError as error:

            await self.send(
                peer_id,
                f"❌ {escape(str(error))}",
            )

            return True

        except (VKAPIError, sqlite3.Error, TypeError, ValueError, KeyError):

            logger.exception("Marriage command operation failed.")

            await self.send(
                peer_id,
                (
                    "❌ Не удалось создать "
                    "предложение."
                ),
            )

            return True

        sender_name = await self.user_name(
            user_id
        )

        target_name = await self.user_name(
            target_id
        )

        notification = (
            "💌 ПРЕДЛОЖЕНИЕ О БРАКЕ\n\n"
            f"👤 {self.mention(user_id, sender_name)} "
            "предлагает тебе заключить игровой брак.\n\n"
            f"💍 Предложение №{proposal_id}\n\n"
            "Если согласен(на):\n"
            "✅ !принять\n\n"
            "Если не согласен(на):\n"
            "❌ !отказать"
        )

        try:

            await self.send(
                target_id,
                notification,
            )

        except (VKAPIError, sqlite3.Error, TypeError, ValueError, KeyError):

            logger.exception("Optional marriage operation failed.")

        await self.send(
            peer_id,
            (
                "💌 ПРЕДЛОЖЕНИЕ ОТПРАВЛЕНО\n\n"
                f"👤 Получатель: "
                f"{self.mention(target_id, target_name)}\n\n"
                f"📨 №{proposal_id}\n"
                "⏳ Ожидаем ответа."
            ),
        )

        return True

    # ========================================================
    # MARRIAGE INFO
    # ========================================================

    async def marriage_text(
        self,
        user_id: int,
    ) -> str:

        marriage = self.db.get_marriage(
            user_id
        )

        if not marriage:

            incoming = (
                self.db.get_pending_proposal_to(
                    user_id
                )
            )

            outgoing = (
                self.db.get_pending_proposal_from(
                    user_id
                )
            )

            text = (
                "💍 БРАК\n\n"
                "У тебя сейчас нет активного брака."
            )

            if incoming:

                from_id = int(
                    incoming["from_user_id"]
                )

                from_name = (
                    await self.user_name(
                        from_id
                    )
                )

                text += (
                    "\n\n"
                    "💌 Тебе сделали предложение:\n"
                    f"{self.mention(from_id, from_name)}\n\n"
                    "✅ !принять\n"
                    "❌ !отказать"
                )

            elif outgoing:

                target_id = int(
                    outgoing["to_user_id"]
                )

                target_name = (
                    await self.user_name(
                        target_id
                    )
                )

                text += (
                    "\n\n"
                    "📨 Твоё предложение:\n"
                    f"{self.mention(target_id, target_name)}\n\n"
                    "🚫 !отменить"
                )

            return text

        user1_id = int(
            marriage["user1_id"]
        )

        user2_id = int(
            marriage["user2_id"]
        )

        if user1_id == int(user_id):

            partner_id = user2_id

        else:

            partner_id = user1_id

        user_name = await self.user_name(
            user_id
        )

        partner_name = await self.user_name(
            partner_id
        )

        xp1, xp2, pair_xp = (
            self.get_pair_xp(
                user_id,
                partner_id,
            )
        )

        days = self.days_between(
            marriage["married_at"]
        )

        date = self.format_date(
            marriage["married_at"]
        )

        return (
            "💍 ВАШ БРАК\n\n"
            f"👤 {self.mention(user_id, user_name)}\n"
            "❤️\n"
            f"👤 {self.mention(partner_id, partner_name)}\n\n"
            f"📅 Вместе: {days} "
            f"{self.plural(days, 'день', 'дня', 'дней')}\n"
            f"💍 Заключён: {date}\n\n"
            "⭐ XP ПАРЫ\n"
            f"👤 Ты: {xp1:,} XP\n"
            f"👤 Партнёр: {xp2:,} XP\n"
            f"💫 Вместе: {pair_xp:,} XP"
        ).replace(
            ",",
            " ",
        )

    # ========================================================
    # !ПРИНЯТЬ
    # ========================================================

    async def command_accept(
        self,
        peer_id: int,
        user_id: int,
    ) -> bool:

        proposal = (
            self.db.get_pending_proposal_to(
                user_id
            )
        )

        if not proposal:

            await self.send(
                peer_id,
                "❌ У тебя нет активных предложений.",
            )

            return True

        proposal_id = int(
            proposal["id"]
        )

        from_user_id = int(
            proposal["from_user_id"]
        )

        marriage = (
            self.db.accept_proposal(
                proposal_id=proposal_id,
                user_id=user_id,
            )
        )

        if not marriage:

            await self.send(
                peer_id,
                (
                    "❌ Не удалось принять предложение.\n\n"
                    "Возможно, у одного из пользователей "
                    "уже появился другой активный брак."
                ),
            )

            return True

        from_name = await self.user_name(
            from_user_id
        )

        to_name = await self.user_name(
            user_id
        )

        _, _, pair_xp = (
            self.get_pair_xp(
                from_user_id,
                user_id,
            )
        )

        date = self.format_date(
            marriage["married_at"]
        )

        announcement = (
            "💍 БРАК ЗАКЛЮЧЁН!\n\n"
            f"👤 {self.mention(from_user_id, from_name)}\n"
            "❤️\n"
            f"👤 {self.mention(user_id, to_name)}\n\n"
            f"📅 Дата: {date}\n"
            f"⭐ XP пары: {pair_xp:,}"
        ).replace(
            ",",
            " ",
        )

        await self.send(
            peer_id,
            announcement,
        )

        if int(peer_id) != from_user_id:

            try:

                await self.send(
                    from_user_id,
                    announcement,
                )

            except Exception:

                pass

        return True

    # ========================================================
    # !ОТКАЗАТЬ
    # ========================================================

    async def command_decline(
        self,
        peer_id: int,
        user_id: int,
    ) -> bool:

        proposal = (
            self.db.get_pending_proposal_to(
                user_id
            )
        )

        if not proposal:

            await self.send(
                peer_id,
                "❌ У тебя нет активных предложений.",
            )

            return True

        proposal_id = int(
            proposal["id"]
        )

        from_user_id = int(
            proposal["from_user_id"]
        )

        declined = (
            self.db.decline_proposal(
                proposal_id=proposal_id,
                user_id=user_id,
            )
        )

        if not declined:

            await self.send(
                peer_id,
                "❌ Предложение уже недоступно.",
            )

            return True

        await self.send(
            peer_id,
            "❌ Предложение отклонено.",
        )

        try:

            user_name = await self.user_name(
                user_id
            )

            await self.send(
                from_user_id,
                (
                    "❌ ПРЕДЛОЖЕНИЕ ОТКЛОНЕНО\n\n"
                    f"{self.mention(user_id, user_name)} "
                    "отклонил(а) твоё предложение."
                ),
            )

        except (VKAPIError, sqlite3.Error, TypeError, ValueError, KeyError):

            logger.exception("Optional marriage operation failed.")

        return True

    # ========================================================
    # !ОТМЕНИТЬ
    # ========================================================

    async def command_cancel(
        self,
        peer_id: int,
        user_id: int,
    ) -> bool:

        proposal = (
            self.db.get_pending_proposal_from(
                user_id
            )
        )

        if not proposal:

            await self.send(
                peer_id,
                "❌ У тебя нет активного предложения.",
            )

            return True

        proposal_id = int(
            proposal["id"]
        )

        target_id = int(
            proposal["to_user_id"]
        )

        cancelled = (
            self.db.cancel_proposal(
                proposal_id=proposal_id,
                user_id=user_id,
            )
        )

        if not cancelled:

            await self.send(
                peer_id,
                "❌ Не удалось отменить предложение.",
            )

            return True

        await self.send(
            peer_id,
            "✅ Предложение отменено.",
        )

        try:

            await self.send(
                target_id,
                "ℹ️ Предложение о браке было отменено.",
            )

        except (VKAPIError, sqlite3.Error, TypeError, ValueError, KeyError):

            logger.exception("Optional marriage operation failed.")

        return True

    # ========================================================
    # !РАЗВОД
    # ========================================================

    async def command_divorce(
        self,
        peer_id: int,
        user_id: int,
    ) -> bool:

        marriage = self.db.get_marriage(
            user_id
        )

        if not marriage:

            await self.send(
                peer_id,
                "❌ У тебя нет активного брака.",
            )

            return True

        user1_id = int(
            marriage["user1_id"]
        )

        user2_id = int(
            marriage["user2_id"]
        )

        if user1_id == int(user_id):

            partner_id = user2_id

        else:

            partner_id = user1_id

        user_name = await self.user_name(
            user_id
        )

        partner_name = await self.user_name(
            partner_id
        )

        old_marriage = self.db.divorce(
            user_id
        )

        if not old_marriage:

            await self.send(
                peer_id,
                "❌ Не удалось расторгнуть брак.",
            )

            return True

        days = self.days_between(
            old_marriage["married_at"],
            old_marriage["divorced_at"],
        )

        message = (
            "💔 БРАК РАСТОРГНУТ\n\n"
            f"👤 {self.mention(user_id, user_name)}\n"
            "❤️\n"
            f"👤 {self.mention(partner_id, partner_name)}\n\n"
            f"📅 Продолжительность: {days} "
            f"{self.plural(days, 'день', 'дня', 'дней')}\n"
            f"💍 Заключён: "
            f"{self.format_date(old_marriage['married_at'])}\n"
            f"💔 Расторгнут: "
            f"{self.format_date(old_marriage['divorced_at'])}"
        )

        await self.send(
            peer_id,
            message,
        )

        if int(peer_id) != partner_id:

            try:

                await self.send(
                    partner_id,
                    (
                        "💔 БРАК РАСТОРГНУТ\n\n"
                        f"{self.mention(user_id, user_name)} "
                        "расторгнул(а) ваш брак."
                    ),
                )

            except Exception:

                pass

        return True

    # ========================================================
    # !ПАРА
    # ========================================================

    async def command_pair(
        self,
        peer_id: int,
        user_id: int,
        args: str,
    ) -> bool:

        if args:

            target_id = self.parse_user_id(
                args
            )

        else:

            target_id = int(
                user_id
            )

        if target_id is None:

            await self.send(
                peer_id,
                (
                    "❌ Не удалось определить пользователя.\n\n"
                    "Пример:\n"
                    "!пара id123"
                ),
            )

            return True

        target_id = int(
            target_id
        )

        marriage = self.db.get_marriage(
            target_id
        )

        target_name = await self.user_name(
            target_id
        )

        if not marriage:

            await self.send(
                peer_id,
                (
                    "👤 "
                    f"{self.mention(target_id, target_name)}\n\n"
                    "💍 Активного брака нет."
                ),
            )

            return True

        user1_id = int(
            marriage["user1_id"]
        )

        user2_id = int(
            marriage["user2_id"]
        )

        if user1_id == target_id:

            partner_id = user2_id

        else:

            partner_id = user1_id

        partner_name = await self.user_name(
            partner_id
        )

        xp1, xp2, pair_xp = (
            self.get_pair_xp(
                target_id,
                partner_id,
            )
        )

        days = self.days_between(
            marriage["married_at"]
        )

        date = self.format_date(
            marriage["married_at"]
        )

        text = (
            "💍 ПАРА\n\n"
            f"👤 {self.mention(target_id, target_name)}\n"
            "❤️\n"
            f"👤 {self.mention(partner_id, partner_name)}\n\n"
            f"📅 Вместе: {days} "
            f"{self.plural(days, 'день', 'дня', 'дней')}\n"
            f"💍 Брак заключён: {date}\n\n"
            "⭐ XP ПАРЫ\n"
            f"👤 {xp1:,} XP\n"
            f"👤 {xp2:,} XP\n"
            f"💫 Вместе: {pair_xp:,} XP"
        ).replace(
            ",",
            " ",
        )

        await self.send(
            peer_id,
            text,
        )

        return True

    # ========================================================
    # !ТОППАР
    # ========================================================

    async def command_top_couples(
        self,
        peer_id: int,
    ) -> bool:

        couples = (
            self.db.get_top_couples(
                limit=10
            )
        )

        if not couples:

            await self.send(
                peer_id,
                (
                    "🏆 ТОП ПАР\n\n"
                    "Пока нет активных браков."
                ),
            )

            return True

        lines = [
            "🏆 ТОП ПАР",
            "",
        ]

        medals = {
            1: "🥇",
            2: "🥈",
            3: "🥉",
        }

        for index, marriage in enumerate(
            couples,
            start=1,
        ):

            user1_id = int(
                marriage["user1_id"]
            )

            user2_id = int(
                marriage["user2_id"]
            )

            name1 = await self.user_name(
                user1_id
            )

            name2 = await self.user_name(
                user2_id
            )

            days = self.days_between(
                marriage["married_at"]
            )

            _, _, pair_xp = (
                self.get_pair_xp(
                    user1_id,
                    user2_id,
                )
            )

            prefix = medals.get(
                index,
                f"{index}.",
            )

            lines.append(
                f"{prefix} "
                f"{self.mention(user1_id, name1)} ❤️ "
                f"{self.mention(user2_id, name2)}"
            )

            lines.append(
                (
                    f"   📅 {days} "
                    f"{self.plural(days, 'день', 'дня', 'дней')}"
                    f" • 💫 {pair_xp:,} XP"
                ).replace(
                    ",",
                    " ",
                )
            )

            lines.append("")

        await self.send(
            peer_id,
            "\n".join(
                lines
            ).strip(),
        )

        return True

    # ========================================================
    # !СТАТБРАК
    # ========================================================

    async def command_statistics(
        self,
        peer_id: int,
    ) -> bool:

        stats = (
            self.db.get_statistics()
        )

        total_proposals = (
            stats["proposals_total"]
        )

        if total_proposals:

            acceptance_percent = (
                stats["proposals_accepted"]
                / total_proposals
            ) * 100

        else:

            acceptance_percent = 0.0

        await self.send(
            peer_id,
            (
                "📊 СТАТИСТИКА БРАКОВ\n\n"
                f"💍 Браков заключено: "
                f"{stats['total_marriages']}\n"
                f"❤️ Активных браков: "
                f"{stats['active_marriages']}\n"
                f"💔 Разводов: "
                f"{stats['divorced_marriages']}\n\n"
                "📨 ПРЕДЛОЖЕНИЯ\n"
                f"📩 Всего: "
                f"{stats['proposals_total']}\n"
                f"✅ Принято: "
                f"{stats['proposals_accepted']}\n"
                f"❌ Отклонено: "
                f"{stats['proposals_declined']}\n"
                f"🚫 Отменено: "
                f"{stats['proposals_cancelled']}\n"
                f"⏳ Ожидают: "
                f"{stats['pending_proposals']}\n\n"
                f"📈 Принято: "
                f"{acceptance_percent:.1f}%"
            ),
        )

        return True

    # ========================================================
    # !ИСТОРИЯБРАКА
    # ========================================================

    async def command_history(
        self,
        peer_id: int,
        user_id: int,
        args: str,
    ) -> bool:

        if args:

            target_id = self.parse_user_id(
                args
            )

        else:

            target_id = int(
                user_id
            )

        if target_id is None:

            await self.send(
                peer_id,
                (
                    "❌ Не удалось определить пользователя.\n\n"
                    "Пример:\n"
                    "!историябрака id123"
                ),
            )

            return True

        target_id = int(
            target_id
        )

        target_name = await self.user_name(
            target_id
        )

        history = self.db.get_history(
            target_id,
            limit=20,
        )

        if not history:

            await self.send(
                peer_id,
                (
                    "📜 ИСТОРИЯ БРАКОВ\n\n"
                    f"👤 {self.mention(target_id, target_name)}\n\n"
                    "История браков отсутствует."
                ),
            )

            return True

        lines = [
            "📜 ИСТОРИЯ БРАКОВ",
            "",
            f"👤 {self.mention(target_id, target_name)}",
            "",
        ]

        for index, marriage in enumerate(
            history,
            start=1,
        ):

            user1_id = int(
                marriage["user1_id"]
            )

            user2_id = int(
                marriage["user2_id"]
            )

            if user1_id == target_id:

                partner_id = user2_id

            else:

                partner_id = user1_id

            partner_name = await self.user_name(
                partner_id
            )

            married_date = self.format_date(
                marriage["married_at"]
            )

            days = self.days_between(
                marriage["married_at"],
                (
                    marriage["divorced_at"]
                    if marriage["divorced_at"]
                    else None
                ),
            )

            if int(
                marriage["active"]
            ) == 1:

                status = "🟢 Активен"

            else:

                status = "💔 Расторгнут"

            lines.append(
                f"{index}. "
                f"{self.mention(partner_id, partner_name)}"
            )

            lines.append(
                f"   💍 {married_date}"
            )

            if marriage["divorced_at"]:

                lines.append(
                    "   💔 "
                    f"{self.format_date(marriage['divorced_at'])}"
                )

            lines.append(
                f"   📅 {days} "
                f"{self.plural(days, 'день', 'дня', 'дней')}"
            )

            lines.append(
                f"   {status}"
            )

            lines.append("")

        await self.send(
            peer_id,
            "\n".join(
                lines
            ).strip(),
        )

        return True

    # ========================================================
    # !БРАКПОМОЩЬ
    # ========================================================

    async def command_help(
        self,
        peer_id: int,
    ) -> bool:

        await self.send(
            peer_id,
            (
                "💍 БРАКИ\n\n"
                "💍 !брак\n"
                "Показать свой текущий брак.\n\n"
                "💌 !брак id123\n"
                "Сделать предложение пользователю.\n\n"
                "✅ !принять\n"
                "Принять входящее предложение.\n\n"
                "❌ !отказать\n"
                "Отклонить входящее предложение.\n\n"
                "🚫 !отменить\n"
                "Отменить своё предложение.\n\n"
                "💔 !развод\n"
                "Расторгнуть текущий брак.\n\n"
                "👥 !пара\n"
                "Показать свою пару.\n\n"
                "👥 !пара id123\n"
                "Показать пару пользователя.\n\n"
                "🏆 !топпар\n"
                "Показать топ активных пар.\n\n"
                "📊 !статбрак\n"
                "Показать статистику браков.\n\n"
                "📜 !историябрака\n"
                "Показать свою историю браков.\n\n"
                "📜 !историябрака id123\n"
                "Показать историю пользователя."
            ),
        )

        return True

    # ========================================================
    # MAIN HANDLER
    # ========================================================

    async def handle_message(
        self,
        peer_id: int,
        user_id: int,
        text: str,
        first_name: str | None = None,
    ) -> bool:

        command, args = self.parse_command(
            text
        )

        if command not in self.COMMANDS:
            return False

        try:

            if command == "!брак":

                return await self.command_marriage(
                    peer_id,
                    user_id,
                    args,
                )

            if command == "!принять":

                return await self.command_accept(
                    peer_id,
                    user_id,
                )

            if command == "!отказать":

                return await self.command_decline(
                    peer_id,
                    user_id,
                )

            if command == "!отменить":

                return await self.command_cancel(
                    peer_id,
                    user_id,
                )

            if command == "!развод":

                return await self.command_divorce(
                    peer_id,
                    user_id,
                )

            if command == "!пара":

                return await self.command_pair(
                    peer_id,
                    user_id,
                    args,
                )

            if command == "!топпар":

                return await self.command_top_couples(
                    peer_id
                )

            if command == "!статбрак":

                return await self.command_statistics(
                    peer_id
                )

            if command == "!историябрака":

                return await self.command_history(
                    peer_id,
                    user_id,
                    args,
                )

            if command == "!бракпомощь":

                return await self.command_help(
                    peer_id
                )

        except (VKAPIError, sqlite3.Error, TypeError, ValueError, KeyError):

            logger.exception("Marriage command operation failed.")

            await self.send(
                peer_id,
                (
                    "❌ При обработке команды произошла ошибка."
                ),
            )

            return True

        return False

    # ========================================================
    # SEND
    # ========================================================

    async def send(
        self,
        peer_id: int,
        message: str,
    ) -> None:

        await self.vk.send_message(
            peer_id=int(peer_id),
            message=str(message),
        )

    # ========================================================
    # CALLBACK
    # ========================================================

    async def handle_callback(
        self,
        event: dict[str, Any],
    ) -> bool:
        """
        В системе браков кнопки не используются.

        Метод оставлен для совместимости
        с main.py.
        """

        return False

    # ========================================================
    # CLOSE
    # ========================================================

    async def close(self) -> None:
        """
        Закрытие модуля.
        SQLite-соединения создаются на каждый запрос,
        поэтому отдельно закрывать здесь нечего.
        """

        return None