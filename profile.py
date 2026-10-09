from __future__ import annotations

import logging
import re
from html import escape

from xp import XPSystem

logger = logging.getLogger("VKBot.Profile")


class ProfileSystem:

    COMMANDS = {"!профиль"}

    def __init__(
        self,
        bot,
        db,
        config,
        marriage=None,
        birthday=None,
    ):
        self.bot = bot
        self.db = db
        self.config = config
        self.marriage = marriage
        self.birthday = birthday

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def user_mention(
        user_id: int,
        first_name: str = "Пользователь",
    ) -> str:

        first_name = (
            str(first_name or "").strip()
            or "Пользователь"
        )

        return (
            f"[id{int(user_id)}|"
            f"{escape(first_name)}]"
        )

    @staticmethod
    def extract_user_id(
        text: str,
    ) -> int | None:

        if not text:
            return None

        patterns = (
            r"\[id(\d+)\|",
            r"\[club(\d+)\|",

            r"\]\(\s*https?://"
            r"(?:www\.)?vk\.(?:ru|com)"
            r"/id(\d+)\s*\)",

            r"https?://"
            r"(?:www\.)?vk\.(?:ru|com)"
            r"/id(\d+)",

            r"@id(\d+)",

            r"\bid(\d+)\b",

            r"(?<!\d)(\d{5,})(?!\d)",
        )

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                re.IGNORECASE,
            )

            if not match:
                continue

            try:
                return int(
                    match.group(1)
                )

            except (
                ValueError,
                TypeError,
            ):
                continue

        return None

    @staticmethod
    def clean_name(
        first_name,
        last_name=None,
    ) -> str:

        parts = []

        if first_name:
            parts.append(
                str(first_name).strip()
            )

        if last_name:
            parts.append(
                str(last_name).strip()
            )

        result = " ".join(
            part
            for part in parts
            if part
        )

        return (
            result
            or "Пользователь"
        )

    @staticmethod
    def progress_bar(
        percent: int,
        length: int = 10,
    ) -> str:

        percent = max(
            0,
            min(100, int(percent)),
        )

        filled = round(
            length * percent / 100
        )

        return (
            "█" * filled
            + "░" * (length - filled)
        )

    # ========================================================
    # ROLE
    # ========================================================

    def get_role(
        self,
        user_id: int,
    ) -> str:

        try:

            admin_ids = (
                self.config.admin_ids
            )

            if int(user_id) in admin_ids:
                return "👑 Администратор"

        except Exception:

            logger.exception(
                "Ошибка определения роли "
                "user_id=%s",
                user_id,
            )

        return "👤 Пользователь"

    # ========================================================
    # MARRIAGE
    # ========================================================

    async def get_marriage_status(
        self,
        user_id: int,
    ) -> str:

        if self.marriage is None:
            return "💍 Не состоит в браке"

        try:

            marriage_db = getattr(
                self.marriage,
                "db",
                None,
            )

            if marriage_db is None:
                return "💍 Не состоит в браке"

            marriage = (
                marriage_db.get_marriage(
                    user_id
                )
            )

            if not marriage:
                return "💍 Не состоит в браке"

            user1_id = int(
                marriage["user1_id"]
            )

            user2_id = int(
                marriage["user2_id"]
            )

            partner_id = (
                user2_id
                if user1_id == int(user_id)
                else user1_id
            )

            partner_name = None

            # ------------------------------------------------
            # ОСНОВНАЯ БД
            # ------------------------------------------------

            try:

                partner = self.db.get_user(
                    partner_id
                )

                if partner:

                    partner_name = (
                        self.clean_name(
                            partner["first_name"],
                            partner["last_name"],
                        )
                    )

            except Exception:

                logger.exception(
                    "Ошибка получения партнёра "
                    "из основной БД: %s",
                    partner_id,
                )

            # ------------------------------------------------
            # MARRIAGE MODULE
            # ------------------------------------------------

            if (
                not partner_name
                and hasattr(
                    self.marriage,
                    "user_name",
                )
            ):

                try:

                    partner_name = (
                        await self.marriage.user_name(
                            partner_id
                        )
                    )

                except Exception:

                    logger.exception(
                        "Ошибка получения имени "
                        "партнёра через MarriageModule: %s",
                        partner_id,
                    )

            # ------------------------------------------------
            # VK
            # ------------------------------------------------

            if not partner_name:

                try:

                    vk_user = (
                        await self.bot.vk.get_user(
                            partner_id
                        )
                    )

                    if vk_user:

                        partner_name = (
                            self.clean_name(
                                vk_user.get(
                                    "first_name"
                                ),
                                vk_user.get(
                                    "last_name"
                                ),
                            )
                        )

                except Exception:

                    logger.exception(
                        "Ошибка получения имени "
                        "партнёра через VK: %s",
                        partner_id,
                    )

            if not partner_name:
                partner_name = "Пользователь"

            return (
                "💍 В браке с "
                f"[id{partner_id}|"
                f"{escape(str(partner_name))}]"
            )

        except Exception:

            logger.exception(
                "Ошибка определения брака "
                "user_id=%s",
                user_id,
            )

            return "💍 Не состоит в браке"

    # ========================================================
    # BIRTHDAY
    # ========================================================

    async def get_birthday_status(
        self,
        user_id: int,
    ) -> str | None:

        if self.birthday is None:
            return None

        try:

            get_report = getattr(
                self.birthday,
                "get_report",
                None,
            )

            if get_report is None:

                get_report = getattr(
                    self.birthday,
                    "get_profile_report",
                    None,
                )

            if get_report is None:
                return None

            result = get_report(
                int(user_id)
            )

            if hasattr(
                result,
                "__await__",
            ):
                result = await result

            if not result:
                return None

            return str(
                result
            ).strip()

        except Exception:

            logger.exception(
                "Ошибка получения дня рождения "
                "user_id=%s",
                user_id,
            )

            return None

    # ========================================================
    # XP
    # ========================================================

    @classmethod
    def calculate_xp_progress(
        cls,
        xp: int,
    ) -> dict[str, int]:
        """Use the same nonlinear XP thresholds as the XP reward system."""
        progress = XPSystem.get_progress_from_xp(max(0, int(xp)))
        return {
            "level": progress.level,
            "current_xp": progress.current_level_xp,
            "level_xp": progress.required_for_next,
            "required_for_next": progress.required_for_next,
            "percent": progress.percent,
            "next_level_xp": progress.remaining_xp,
            "total_xp": progress.total_xp,
        }

    @staticmethod
    def get_progress_text(
        percent: int,
    ) -> str:

        if percent < 25:
            return "🌱 Путь только начинается"

        if percent < 50:
            return "🌿 Хорошее начало"

        if percent < 75:
            return "🔥 Отличный прогресс"

        if percent < 100:
            return "🚀 Почти новый уровень"

        return "🏆 Новый уровень совсем близко"

    # ========================================================
    # PROFILE
    # ========================================================

    async def build_profile(
        self,
        user_id: int,
    ) -> str | None:

        try:

            user = self.db.get_user(
                user_id
            )

        except Exception:

            logger.exception(
                "Ошибка получения профиля "
                "user_id=%s",
                user_id,
            )

            return None

        if not user:
            return None

        # ----------------------------------------------------
        # NAME
        # ----------------------------------------------------

        first_name = (
            user["first_name"]
            or "Пользователь"
        )

        last_name = (
            user["last_name"]
            or ""
        )

        full_name = self.clean_name(
            first_name,
            last_name,
        )

        mention = self.user_mention(
            user_id,
            full_name,
        )

        # ----------------------------------------------------
        # WARNINGS
        # ----------------------------------------------------

        try:

            warnings = (
                self.db.get_warning_count(
                    user_id
                )
            )

        except Exception:

            logger.exception(
                "Ошибка получения предупреждений "
                "user_id=%s",
                user_id,
            )

            warnings = 0

        # ----------------------------------------------------
        # ACTIVITY
        # ----------------------------------------------------

        try:

            messages = int(
                user["messages"] or 0
            )

        except (
            IndexError,
            KeyError,
            TypeError,
            ValueError,
        ):

            messages = 0

        try:

            rp_count = int(
                user["rp_count"] or 0
            )

        except (
            IndexError,
            KeyError,
            TypeError,
            ValueError,
        ):

            rp_count = 0

        try:

            xp = int(
                user["xp"] or 0
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ):

            xp = 0

        # ----------------------------------------------------
        # XP
        # ----------------------------------------------------

        progress = (
            self.calculate_xp_progress(
                xp
            )
        )

        level = progress["level"]

        current_xp = (
            progress["current_xp"]
        )

        level_xp = (
            progress["level_xp"]
        )

        percent = (
            progress["percent"]
        )

        next_level_xp = (
            progress["next_level_xp"]
        )

        total_xp = (
            progress["total_xp"]
        )

        bar = self.progress_bar(
            percent
        )

        progress_text = (
            self.get_progress_text(
                percent
            )
        )

        # ----------------------------------------------------
        # ROLE
        # ----------------------------------------------------

        role = self.get_role(
            user_id
        )

        # ----------------------------------------------------
        # MARRIAGE
        # ----------------------------------------------------

        marriage_status = (
            await self.get_marriage_status(
                user_id
            )
        )

        # ----------------------------------------------------
        # BIRTHDAY
        # ----------------------------------------------------

        birthday_status = (
            await self.get_birthday_status(
                user_id
            )
        )

        # ----------------------------------------------------
        # PROFILE HEADER
        # ----------------------------------------------------

        lines = [
            "👤 ПРОФИЛЬ",
            "",
            f"Пользователь: {mention}",
            f"🔗 [id{user_id}|Открыть профиль]",
            "",
            "💠 СТАТУС",
            "",
            role,
            marriage_status,
        ]

        # ----------------------------------------------------
        # BIRTHDAY
        # ----------------------------------------------------

        if birthday_status:

            lines.extend(
                [
                    "",
                    birthday_status,
                ]
            )

        # ----------------------------------------------------
        # ACTIVITY + XP
        # ----------------------------------------------------

        lines.extend(
            [
                "",
                "📊 АКТИВНОСТЬ",
                "",
                f"💬 Сообщений: {messages}",
                f"🎭 RP-действий: {rp_count}",
                "",
                "⭐ ПРОГРЕСС",
                "",
                f"🏆 Уровень: {level}",
                "",
                f"{bar} {percent}%",
                "",
                f"💎 XP: {current_xp} / {level_xp}",
                f"🔥 До следующего уровня: "
                f"{next_level_xp} XP",
                f"📈 Всего XP: {total_xp}",
                "",
                progress_text,
                "",
                f"⚠️ Предупреждений: {warnings}",
            ]
        )

        return "\n".join(
            lines
        )

    async def _reply(self, peer_id: int, message: str) -> None:
        sender = getattr(self.bot, "reply", None)
        if callable(sender):
            await sender(int(peer_id), str(message))
            return

        sender = getattr(self.bot, "send_message", None)
        if callable(sender):
            await sender(peer_id=int(peer_id), message=str(message))
            return

        raise RuntimeError("ProfileSystem bot does not support replying.")

    # ========================================================
    # SHOW PROFILE
    # ========================================================

    async def show_profile(
        self,
        peer_id: int,
        user_id: int,
    ):

        profile = await self.build_profile(
            user_id
        )

        if profile is None:

            await self._reply(
                peer_id,
                "❌ Профиль ещё не создан.",
            )

            return

        await self._reply(
            peer_id,
            profile,
        )

    # ========================================================
    # COMMAND
    # ========================================================

    async def handle_message(
        self,
        peer_id: int,
        user_id: int,
        text: str,
        first_name: str | None = None,
    ) -> bool:
        return await self.handle_command(peer_id, user_id, text)

    async def handle_command(
        self,
        peer_id: int,
        sender_id: int,
        text: str,
    ) -> bool:

        normalized = (
            str(text or "")
            .strip()
            .casefold()
        )

        if not (
            normalized in {"!профиль", "/профиль"}
            or normalized.startswith("!профиль ")
            or normalized.startswith("/профиль ")
        ):

            return False

        target_id = (
            self.extract_user_id(
                text
            )
        )

        if target_id is None:
            target_id = sender_id

        await self.show_profile(
            peer_id=peer_id,
            user_id=target_id,
        )

        return True