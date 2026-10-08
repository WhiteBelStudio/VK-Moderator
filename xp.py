from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Any

from database import Database


# =========================================================
# XP PROGRESS
# =========================================================

@dataclass(frozen=True)
class XPProgress:
    level: int
    total_xp: int

    # XP внутри текущего уровня.
    current_level_xp: int

    # Сколько XP нужно всего внутри текущего уровня
    # для перехода на следующий.
    required_for_next: int

    # Сколько XP осталось до следующего уровня.
    remaining_xp: int

    # Процент прогресса текущего уровня.
    percent: int


# =========================================================
# XP REWARD
# =========================================================

@dataclass(frozen=True)
class XPReward:
    action: str
    base_xp: int
    multiplier: float
    final_xp: int


# =========================================================
# XP SYSTEM
# =========================================================

class XPSystem:
    """
    Расширенная система XP.

    ВАЖНО:

    XP внутри уровня начинается с 0.

    Например:

        Уровень 1
        0 / 250 XP

        100 / 250 XP

        переход на уровень 2

        Уровень 2
        0 / 600 XP

    При этом общий XP сохраняется отдельно.

    Система включает:

    • нелинейные уровни
    • до 1000 уровней
    • XP за разные действия
    • cooldown
    • защиту от спама
    • дневной лимит
    • streak
    • множитель за streak
    • достижения
    • звания
    • ежедневные задания
    • большие рубежи
    • XP TOP
    """

    # =====================================================
    # GENERAL SETTINGS
    # =====================================================

    MAX_LEVEL = 1000

    LEVEL_BASE = 150

    LEVEL_GROWTH = 1.18

    # =====================================================
    # MESSAGE SETTINGS
    # =====================================================

    MESSAGE_XP = 3

    MESSAGE_COOLDOWN = 30

    DAILY_MESSAGE_XP_LIMIT = 300

    # =====================================================
    # ACTION REWARDS
    # =====================================================

    REWARDS = {
        "message": 3,

        "profile_created": 100,
        "profile_completed": 150,

        "search": 5,
        "profile_view": 2,

        "like": 5,
        "match": 50,

        "favorite": 5,

        "review": 25,

        "daily": 50,

        "streak_3": 25,
        "streak_7": 100,
        "streak_14": 250,
        "streak_30": 500,
        "streak_60": 1000,
        "streak_100": 2500,
    }

    # =====================================================
    # TITLES
    # =====================================================

    TITLES = (
        (1, "🌱 Новичок"),
        (5, "🔎 Исследователь"),
        (10, "🌿 Активист"),
        (20, "🔥 Общительный"),
        (30, "⚡ Постоянный"),
        (50, "💎 Опытный"),
        (75, "🏆 Продвинутый"),
        (100, "👑 Ветеран"),
        (150, "💫 Элита"),
        (200, "⚔️ Мастер"),
        (300, "🌟 Легенда"),
        (400, "💠 Грандмастер"),
        (500, "👑 Император"),
        (750, "🚀 Титан"),
        (1000, "🌌 Абсолют"),
    )

    # =====================================================
    # ACHIEVEMENTS
    # =====================================================

    ACHIEVEMENTS = {
        "first_message": {
            "title": "💬 Первое сообщение",
            "description": "Отправь первое сообщение.",
            "xp": 25,
        },

        "messages_10": {
            "title": "💬 Общительный",
            "description": "Отправь 10 сообщений.",
            "xp": 50,
        },

        "messages_100": {
            "title": "🔥 Болтун",
            "description": "Отправь 100 сообщений.",
            "xp": 250,
        },

        "messages_500": {
            "title": "⚡ Активный участник",
            "description": "Отправь 500 сообщений.",
            "xp": 750,
        },

        "messages_1000": {
            "title": "👑 Главный активист",
            "description": "Отправь 1000 сообщений.",
            "xp": 1500,
        },

        "first_match": {
            "title": "🤝 Первое совпадение",
            "description": "Получи первое совпадение.",
            "xp": 100,
        },

        "matches_10": {
            "title": "🤝 Социальный",
            "description": "Получи 10 совпадений.",
            "xp": 500,
        },

        "matches_50": {
            "title": "🌟 Популярный",
            "description": "Получи 50 совпадений.",
            "xp": 2000,
        },

        "xp_1000": {
            "title": "💎 1000 XP",
            "description": "Набери 1000 XP.",
            "xp": 100,
        },

        "xp_10000": {
            "title": "💎 10000 XP",
            "description": "Набери 10000 XP.",
            "xp": 500,
        },

        "level_10": {
            "title": "🏆 10 уровень",
            "description": "Достигни 10 уровня.",
            "xp": 100,
        },

        "level_50": {
            "title": "👑 50 уровень",
            "description": "Достигни 50 уровня.",
            "xp": 500,
        },

        "level_100": {
            "title": "👑 100 уровень",
            "description": "Достигни 100 уровня.",
            "xp": 2000,
        },

        "streak_7": {
            "title": "🔥 Неделя активности",
            "description": "Будь активен 7 дней подряд.",
            "xp": 250,
        },

        "streak_30": {
            "title": "🔥 Месяц активности",
            "description": "Будь активен 30 дней подряд.",
            "xp": 1000,
        },
    }

    # =====================================================
    # INIT
    # =====================================================

    def __init__(
        self,
        db: Database | None = None,
    ):
        self.db = db

        # Временные cooldown.
        self._cooldowns: dict[
            tuple[int, str],
            float,
        ] = {}

        # Дневной XP.
        self._daily_xp: dict[
            int,
            tuple[str, int],
        ] = {}

        # Streak.
        self._streaks: dict[
            int,
            dict[str, Any],
        ] = {}

        # Достижения.
        self._achievements: dict[
            int,
            set[str],
        ] = {}

        # Статистика действий.
        self._stats: dict[
            int,
            dict[str, int],
        ] = {}

    # =====================================================
    # DATABASE
    # =====================================================

    def _get_db(self) -> Database:
        if self.db is None:
            raise RuntimeError(
                "XPSystem: база данных не подключена."
            )

        return self.db

    # =====================================================
    # LEVEL XP
    # =====================================================

    @classmethod
    def xp_for_level(
        cls,
        level: int,
    ) -> int:
        """
        Возвращает ОБЩИЙ XP-порог уровня.

        Например:

            xp_for_level(1) = 0
            xp_for_level(2) = ...
            xp_for_level(3) = ...

        Эти значения используются только
        для определения уровня.

        Пользовательский прогресс при этом
        показывается относительно текущего уровня.
        """

        level = max(
            1,
            int(level),
        )

        if level <= 1:
            return 0

        total = 0.0

        for current in range(1, level):

            required = (
                cls.LEVEL_BASE
                * (current ** 0.75)
                * (
                    cls.LEVEL_GROWTH
                    ** (current / 20)
                )
            )

            total += required

        return int(total)

    # =====================================================
    # LEVEL FROM XP
    # =====================================================

    @classmethod
    def calculate_level(
        cls,
        xp: int,
    ) -> int:

        xp = max(
            0,
            int(xp),
        )

        if xp <= 0:
            return 1

        low = 1
        high = cls.MAX_LEVEL

        while low < high:

            mid = (
                low
                + high
                + 1
            ) // 2

            if cls.xp_for_level(mid) <= xp:
                low = mid

            else:
                high = mid - 1

        return low

    # =====================================================
    # NEXT LEVEL
    # =====================================================

    @classmethod
    def next_level_xp(
        cls,
        level: int,
    ) -> int:

        level = max(
            1,
            int(level),
        )

        if level >= cls.MAX_LEVEL:

            return cls.xp_for_level(
                cls.MAX_LEVEL
            )

        return cls.xp_for_level(
            level + 1
        )

    # =====================================================
    # PROGRESS
    # =====================================================

    @classmethod
    def get_progress_from_xp(
        cls,
        xp: int,
    ) -> XPProgress:
        """
        ВАЖНО:

        current_level_xp — XP именно внутри
        текущего уровня.

        Например:

            Общий XP = 850

            Текущий уровень = 3

            Порог уровня 3 = 600

            Значит:

            current_level_xp = 850 - 600
                              = 250

        Пользователь увидит:

            💎 XP: 250 / 450

        А не:

            💎 XP: 850 / 1050
        """

        xp = max(
            0,
            int(xp),
        )

        level = cls.calculate_level(
            xp
        )

        # =================================================
        # ТЕКУЩИЙ ПОРОГ
        # =================================================

        current_threshold = (
            cls.xp_for_level(
                level
            )
        )

        # =================================================
        # СЛЕДУЮЩИЙ ПОРОГ
        # =================================================

        next_threshold = (
            cls.next_level_xp(
                level
            )
        )

        # =================================================
        # MAX LEVEL
        # =================================================

        if level >= cls.MAX_LEVEL:

            return XPProgress(
                level=level,
                total_xp=xp,

                # После максимального уровня
                # показываем XP сверх порога.
                current_level_xp=max(
                    0,
                    xp - current_threshold,
                ),

                required_for_next=0,
                remaining_xp=0,
                percent=100,
            )

        # =================================================
        # XP ВНУТРИ ТЕКУЩЕГО УРОВНЯ
        # =================================================

        current_level_xp = (
            xp
            - current_threshold
        )

        current_level_xp = max(
            0,
            current_level_xp,
        )

        # =================================================
        # СКОЛЬКО XP НУЖНО ДЛЯ УРОВНЯ
        # =================================================

        required_for_next = (
            next_threshold
            - current_threshold
        )

        required_for_next = max(
            1,
            required_for_next,
        )

        # =================================================
        # XP ДО СЛЕДУЮЩЕГО
        # =================================================

        remaining_xp = max(
            0,
            next_threshold - xp,
        )

        # =================================================
        # ПРОЦЕНТ
        # =================================================

        percent = int(
            (
                current_level_xp
                / required_for_next
            )
            * 100
        )

        percent = max(
            0,
            min(
                100,
                percent,
            ),
        )

        return XPProgress(
            level=level,
            total_xp=xp,
            current_level_xp=current_level_xp,
            required_for_next=required_for_next,
            remaining_xp=remaining_xp,
            percent=percent,
        )

    # =====================================================
    # USER XP
    # =====================================================

    def get_user_xp(
        self,
        user_id: int,
    ) -> dict:

        db = self._get_db()

        user = db.get_user(
            user_id
        )

        if not user:

            return {
                "xp": 0,
                "level": 1,
            }

        xp = int(
            user["xp"] or 0
        )

        level = (
            self.calculate_level(
                xp
            )
        )

        return {
            "xp": xp,
            "level": level,
        }

    # =====================================================
    # STREAK
    # =====================================================

    def _get_streak(
        self,
        user_id: int,
    ) -> dict:

        data = self._streaks.get(
            user_id
        )

        if data is None:

            data = {
                "days": 0,
                "last_date": None,
            }

            self._streaks[
                user_id
            ] = data

        return data

    def update_streak(
        self,
        user_id: int,
    ) -> dict:

        today = date.today().isoformat()

        streak = self._get_streak(
            user_id
        )

        last_date = streak.get(
            "last_date"
        )

        # Уже был активен сегодня.
        if last_date == today:

            return {
                "days": streak["days"],
                "new_day": False,
                "bonus": 0,
            }

        # Первый день.
        if not last_date:

            streak["days"] = 1

        else:

            try:

                previous = (
                    date.fromisoformat(
                        last_date
                    )
                )

                difference = (
                    date.today()
                    - previous
                ).days

            except ValueError:

                difference = 999

            if difference == 1:

                streak["days"] += 1

            else:

                streak["days"] = 1

        streak["last_date"] = today

        bonus = 0

        if streak["days"] == 3:

            bonus = self.REWARDS[
                "streak_3"
            ]

        elif streak["days"] == 7:

            bonus = self.REWARDS[
                "streak_7"
            ]

        elif streak["days"] == 14:

            bonus = self.REWARDS[
                "streak_14"
            ]

        elif streak["days"] == 30:

            bonus = self.REWARDS[
                "streak_30"
            ]

        elif streak["days"] == 60:

            bonus = self.REWARDS[
                "streak_60"
            ]

        elif streak["days"] == 100:

            bonus = self.REWARDS[
                "streak_100"
            ]

        return {
            "days": streak["days"],
            "new_day": True,
            "bonus": bonus,
        }

    # =====================================================
    # STREAK MULTIPLIER
    # =====================================================

    def get_streak_multiplier(
        self,
        user_id: int,
    ) -> float:

        days = self._get_streak(
            user_id
        )["days"]

        if days >= 100:
            return 2.5

        if days >= 60:
            return 2.0

        if days >= 30:
            return 1.75

        if days >= 14:
            return 1.5

        if days >= 7:
            return 1.35

        if days >= 3:
            return 1.15

        return 1.0

    # =====================================================
    # DAILY XP
    # =====================================================

    def _get_daily_data(
        self,
        user_id: int,
    ) -> tuple[str, int]:

        today = date.today().isoformat()

        data = self._daily_xp.get(
            user_id
        )

        if not data:

            data = (
                today,
                0,
            )

        if data[0] != today:

            data = (
                today,
                0,
            )

        self._daily_xp[
            user_id
        ] = data

        return data

    # =====================================================
    # COOLDOWN
    # =====================================================

    def can_receive_xp(
        self,
        user_id: int,
        action: str,
        cooldown: int | None = None,
    ) -> bool:

        if cooldown is None:

            if action == "message":

                cooldown = (
                    self.MESSAGE_COOLDOWN
                )

            else:

                cooldown = 0

        if cooldown <= 0:
            return True

        key = (
            user_id,
            action,
        )

        last = self._cooldowns.get(
            key
        )

        if last is None:
            return True

        return (
            time.time() - last
            >= cooldown
        )

    def _set_cooldown(
        self,
        user_id: int,
        action: str,
    ) -> None:

        self._cooldowns[
            (
                user_id,
                action,
            )
        ] = time.time()

    # =====================================================
    # STATS
    # =====================================================

    def _increment_stat(
        self,
        user_id: int,
        action: str,
    ) -> int:

        stats = self._stats.setdefault(
            user_id,
            {},
        )

        stats[action] = (
            stats.get(
                action,
                0,
            )
            + 1
        )

        return stats[action]

    def get_stats(
        self,
        user_id: int,
    ) -> dict[str, int]:

        return dict(
            self._stats.get(
                user_id,
                {},
            )
        )

    # =====================================================
    # ADD XP
    # =====================================================

    def add_xp(
        self,
        user_id: int,
        amount: int,
        action: str = "manual",
        apply_multiplier: bool = False,
    ) -> dict:

        db = self._get_db()

        amount = int(
            amount
        )

        current = self.get_user_xp(
            user_id
        )

        old_xp = int(
            current["xp"]
        )

        old_level = int(
            current["level"]
        )

        # =================================================
        # INVALID XP
        # =================================================

        if amount <= 0:

            return {
                "old_xp": old_xp,
                "new_xp": old_xp,
                "old_level": old_level,
                "new_level": old_level,

                "level_up": False,

                "milestone": False,
                "milestone_level": None,
                "milestones": [],

                "xp_added": 0,

                "multiplier": 1.0,

                "progress": (
                    self.get_progress_from_xp(
                        old_xp
                    )
                ),
            }

        # =================================================
        # MULTIPLIER
        # =================================================

        multiplier = 1.0

        if apply_multiplier:

            multiplier = (
                self.get_streak_multiplier(
                    user_id
                )
            )

        final_amount = int(
            round(
                amount
                * multiplier
            )
        )

        # =================================================
        # DAILY MESSAGE LIMIT
        # =================================================

        if action == "message":

            today, used = (
                self._get_daily_data(
                    user_id
                )
            )

            available = max(
                0,
                self.DAILY_MESSAGE_XP_LIMIT
                - used,
            )

            final_amount = min(
                final_amount,
                available,
            )

            self._daily_xp[
                user_id
            ] = (
                today,
                used + final_amount,
            )

        # =================================================
        # NOTHING TO ADD
        # =================================================

        if final_amount <= 0:

            return {
                "old_xp": old_xp,
                "new_xp": old_xp,
                "old_level": old_level,
                "new_level": old_level,

                "level_up": False,

                "milestone": False,
                "milestone_level": None,
                "milestones": [],

                "xp_added": 0,

                "multiplier": multiplier,

                "progress": (
                    self.get_progress_from_xp(
                        old_xp
                    )
                ),
            }

        # =================================================
        # NEW TOTAL XP
        # =================================================

        new_xp = (
            old_xp
            + final_amount
        )

        # =================================================
        # NEW LEVEL
        # =================================================

        new_level = (
            self.calculate_level(
                new_xp
            )
        )

        level_up = (
            new_level
            > old_level
        )

        # =================================================
        # MILESTONES
        # =================================================

        milestones: list[int] = []

        if level_up:

            first_milestone = (
                (
                    old_level
                    // 100
                )
                + 1
            ) * 100

            last_milestone = (
                new_level
                // 100
            ) * 100

            if (
                first_milestone
                <= last_milestone
            ):

                milestones = list(
                    range(
                        first_milestone,
                        last_milestone + 1,
                        100,
                    )
                )

        # =================================================
        # SAVE
        # =================================================

        db.update_xp(
            user_id=user_id,
            xp=new_xp,
            level=new_level,
        )

        # =================================================
        # STATS
        # =================================================

        if action:

            self._increment_stat(
                user_id,
                action,
            )

        # =================================================
        # PROGRESS
        # =================================================

        progress = (
            self.get_progress_from_xp(
                new_xp
            )
        )

        # =================================================
        # ACHIEVEMENTS
        # =================================================

        achievements = (
            self.check_achievements(
                user_id
            )
        )

        return {
            "old_xp": old_xp,
            "new_xp": new_xp,

            "old_level": old_level,
            "new_level": new_level,

            "level_up": level_up,

            "milestone": bool(
                milestones
            ),

            "milestone_level": (
                milestones[-1]
                if milestones
                else None
            ),

            "milestones": milestones,

            "xp_added": final_amount,

            "multiplier": multiplier,

            "action": action,

            "achievements": achievements,

            "progress": progress,
        }

    # =====================================================
    # REWARD
    # =====================================================

    def reward(
        self,
        user_id: int,
        action: str,
        amount: int | None = None,
        cooldown: int | None = None,
        multiplier: bool = True,
    ) -> dict:

        if amount is None:

            amount = self.REWARDS.get(
                action,
                0,
            )

        if amount <= 0:

            return {
                "success": False,
                "reason": "unknown_action",
            }

        if not self.can_receive_xp(
            user_id=user_id,
            action=action,
            cooldown=cooldown,
        ):

            return {
                "success": False,
                "reason": "cooldown",
                "xp_added": 0,
            }

        self._set_cooldown(
            user_id,
            action,
        )

        # =================================================
        # STREAK
        # =================================================

        streak_result = (
            self.update_streak(
                user_id
            )
        )

        # =================================================
        # MAIN REWARD
        # =================================================

        result = self.add_xp(
            user_id=user_id,
            amount=amount,
            action=action,
            apply_multiplier=multiplier,
        )

        # =================================================
        # STREAK BONUS
        # =================================================

        streak_bonus = (
            streak_result["bonus"]
        )

        if streak_bonus > 0:

            bonus_result = self.add_xp(
                user_id=user_id,
                amount=streak_bonus,
                action="streak_bonus",
                apply_multiplier=False,
            )

            result["streak_bonus"] = (
                bonus_result["xp_added"]
            )

        else:

            result["streak_bonus"] = 0

        result["streak"] = (
            streak_result["days"]
        )

        result["success"] = True

        return result

    # =====================================================
    # MESSAGE XP
    # =====================================================

    def add_message_xp(
        self,
        user_id: int,
        amount: int | None = None,
    ) -> dict:

        if amount is None:

            amount = (
                self.MESSAGE_XP
            )

        return self.reward(
            user_id=user_id,
            action="message",
            amount=amount,
            cooldown=self.MESSAGE_COOLDOWN,
            multiplier=True,
        )

    # =====================================================
    # PROCESS MESSAGE
    # =====================================================

    def process_message(
        self,
        user_id: int,
        amount: int | None = None,
    ) -> dict:

        return self.add_message_xp(
            user_id=user_id,
            amount=amount,
        )

    # =====================================================
    # ACTION REWARD
    # =====================================================

    def reward_action(
        self,
        user_id: int,
        action: str,
    ) -> dict:

        return self.reward(
            user_id=user_id,
            action=action,
            multiplier=True,
        )

    # =====================================================
    # ACHIEVEMENTS
    # =====================================================

    def _get_achievements(
        self,
        user_id: int,
    ) -> set[str]:

        return self._achievements.setdefault(
            user_id,
            set(),
        )

    def check_achievements(
        self,
        user_id: int,
    ) -> list[dict]:

        stats = self.get_stats(
            user_id
        )

        xp_data = self.get_user_xp(
            user_id
        )

        xp = xp_data["xp"]

        level = xp_data["level"]

        unlocked = (
            self._get_achievements(
                user_id
            )
        )

        result = []

        checks = {
            "first_message": (
                stats.get(
                    "message",
                    0,
                )
                >= 1
            ),

            "messages_10": (
                stats.get(
                    "message",
                    0,
                )
                >= 10
            ),

            "messages_100": (
                stats.get(
                    "message",
                    0,
                )
                >= 100
            ),

            "messages_500": (
                stats.get(
                    "message",
                    0,
                )
                >= 500
            ),

            "messages_1000": (
                stats.get(
                    "message",
                    0,
                )
                >= 1000
            ),

            "first_match": (
                stats.get(
                    "match",
                    0,
                )
                >= 1
            ),

            "matches_10": (
                stats.get(
                    "match",
                    0,
                )
                >= 10
            ),

            "matches_50": (
                stats.get(
                    "match",
                    0,
                )
                >= 50
            ),

            "xp_1000": xp >= 1000,

            "xp_10000": xp >= 10000,

            "level_10": level >= 10,

            "level_50": level >= 50,

            "level_100": level >= 100,

            "streak_7": (
                self._get_streak(
                    user_id
                )["days"]
                >= 7
            ),

            "streak_30": (
                self._get_streak(
                    user_id
                )["days"]
                >= 30
            ),
        }

        for (
            achievement_id,
            completed,
        ) in checks.items():

            if not completed:
                continue

            if achievement_id in unlocked:
                continue

            achievement = (
                self.ACHIEVEMENTS.get(
                    achievement_id
                )
            )

            if not achievement:
                continue

            unlocked.add(
                achievement_id
            )

            reward_xp = int(
                achievement["xp"]
            )

            try:

                self.add_xp(
                    user_id=user_id,
                    amount=reward_xp,
                    action="achievement",
                    apply_multiplier=False,
                )

            except Exception:
                pass

            result.append({
                "id": achievement_id,
                **achievement,
            })

        return result

    # =====================================================
    # TITLE
    # =====================================================

    @classmethod
    def get_title(
        cls,
        level: int,
    ) -> str:

        level = int(level)

        current = cls.TITLES[0][1]

        for (
            required_level,
            title,
        ) in cls.TITLES:

            if level >= required_level:

                current = title

            else:

                break

        return current

    # =====================================================
    # NEXT TITLE
    # =====================================================

    @classmethod
    def get_next_title(
        cls,
        level: int,
    ) -> tuple[int, str] | None:

        level = int(level)

        for (
            required_level,
            title,
        ) in cls.TITLES:

            if level < required_level:

                return (
                    required_level,
                    title,
                )

        return None

    # =====================================================
    # PROGRESS BAR
    # =====================================================

    @staticmethod
    def progress_bar(
        percent: int,
        size: int = 12,
    ) -> str:

        percent = max(
            0,
            min(
                100,
                int(percent),
            ),
        )

        filled = round(
            size
            * percent
            / 100
        )

        filled = max(
            0,
            min(
                size,
                filled,
            ),
        )

        return (
            "🟩" * filled
            + "⬜" * (
                size - filled
            )
        )

    # =====================================================
    # PROGRESS DESCRIPTION
    # =====================================================

    @staticmethod
    def progress_description(
        percent: int,
    ) -> str:

        if percent < 10:

            return (
                "🌱 Только начинаешь прокачку"
            )

        if percent < 25:

            return (
                "🌿 Первые шаги сделаны"
            )

        if percent < 50:

            return (
                "🔥 Хороший темп"
            )

        if percent < 75:

            return (
                "⚡ Ты серьёзно набираешь обороты"
            )

        if percent < 90:

            return (
                "🚀 Почти новый уровень"
            )

        if percent < 100:

            return (
                "👑 Осталось совсем немного"
            )

        return (
            "🏆 Уровень достигнут"
        )

    # =====================================================
    # STREAK TEXT
    # =====================================================

    def streak_text(
        self,
        user_id: int,
    ) -> str:

        streak = self._get_streak(
            user_id
        )

        days = streak["days"]

        multiplier = (
            self.get_streak_multiplier(
                user_id
            )
        )

        if days <= 0:

            return (
                "🔥 Серия активности: 0 дней\n"
                "Начни активничать сегодня!"
            )

        return (
            f"🔥 Серия активности: "
            f"{days} дн.\n"
            f"⚡ Множитель XP: "
            f"×{multiplier:g}"
        )

    # =====================================================
    # XP PROFILE
    # =====================================================

    def profile_text(
        self,
        user_id: int,
        user_name: str = "Пользователь",
    ) -> str:

        data = self.get_user_xp(
            user_id
        )

        progress = (
            self.get_progress_from_xp(
                data["xp"]
            )
        )

        title = self.get_title(
            progress.level
        )

        bar = self.progress_bar(
            progress.percent
        )

        next_title = (
            self.get_next_title(
                progress.level
            )
        )

        # =================================================
        # ОСНОВНОЙ ТЕКСТ
        # =================================================

        text = (
            "⭐ <b>XP ПРОФИЛЬ</b>\n\n"

            f"👤 <b>{user_name}</b>\n\n"

            f"🏆 Уровень: "
            f"<b>{progress.level}</b>\n"

            f"🎖️ Звание: "
            f"<b>{title}</b>\n\n"

            f"{bar} "
            f"<b>{progress.percent}%</b>\n\n"

            # ВАЖНО:
            # теперь здесь XP внутри уровня.
            f"💎 XP: "
            f"<b>{progress.current_level_xp}</b>"
            f" / "
            f"<b>{progress.required_for_next}</b>\n"

            f"🔥 До следующего уровня: "
            f"<b>{progress.remaining_xp} XP</b>\n"

            f"📈 Всего XP: "
            f"<b>{progress.total_xp}</b>\n\n"

            f"{self.progress_description(progress.percent)}\n\n"

            f"{self.streak_text(user_id)}"
        )

        # =================================================
        # NEXT TITLE
        # =================================================

        if next_title:

            required_level, next_title_name = (
                next_title
            )

            text += (
                "\n\n"
                f"🎯 Следующее звание: "
                f"<b>{next_title_name}</b>\n"

                f"🏆 Нужно достичь "
                f"<b>{required_level}</b> уровня"
            )

        return text

    # =====================================================
    # OLD COMPATIBILITY
    # =====================================================

    def progress_text(
        self,
        user_id: int,
    ) -> str:

        return self.profile_text(
            user_id=user_id
        )

    # =====================================================
    # LEVEL UP
    # =====================================================

    @classmethod
    def level_up_text(
        cls,
        old_level: int,
        new_level: int,
        total_xp: int,
    ) -> str:

        title = cls.get_title(
            new_level
        )

        if (
            new_level
            - old_level
            == 1
        ):

            level_line = (
                f"🏆 {old_level} → "
                f"{new_level} уровень"
            )

        else:

            level_line = (
                f"🏆 {old_level} → "
                f"{new_level} уровни"
            )

        # После повышения текущий XP
        # внутри нового уровня начинается с 0.

        progress = (
            cls.get_progress_from_xp(
                total_xp
            )
        )

        return (
            "🎉 <b>НОВЫЙ УРОВЕНЬ!</b>\n\n"

            f"{level_line}\n\n"

            f"🎖️ Новое звание: "
            f"<b>{title}</b>\n\n"

            f"💎 XP нового уровня: "
            f"<b>{progress.current_level_xp}</b>"
            f" / "
            f"<b>{progress.required_for_next}</b>\n\n"

            f"📈 Всего XP: "
            f"<b>{total_xp}</b>\n\n"

            "🔥 Отличная работа!\n"
            "Продолжай активничать."
        )

    # =====================================================
    # ACHIEVEMENT TEXT
    # =====================================================

    @staticmethod
    def achievement_text(
        achievement: dict,
    ) -> str:

        return (
            "🏆 <b>НОВОЕ ДОСТИЖЕНИЕ!</b>\n\n"

            f"{achievement['title']}\n\n"

            f"📌 "
            f"{achievement['description']}\n"

            f"💎 Награда: "
            f"+{achievement['xp']} XP"
        )

    # =====================================================
    # MILESTONE TEXT
    # =====================================================

    @staticmethod
    def milestone_text(
        user_name: str,
        level: int,
        total_xp: int,
    ) -> str:

        user_name = (
            str(user_name).strip()
            or "Пользователь"
        )

        special = {

            100: (
                "🎉 ПЕРВЫЙ БОЛЬШОЙ РУБЕЖ!",
                "Ты достиг невероятных 100 уровня!",
            ),

            200: (
                "💎 200 УРОВЕНЬ!",
                "Ты уже настоящий ветеран сообщества!",
            ),

            300: (
                "👑 300 УРОВЕНЬ!",
                "Это уже легендарный результат!",
            ),

            400: (
                "🔥 400 УРОВЕНЬ!",
                "Ты продолжаешь покорять вершины!",
            ),

            500: (
                "🏆 500 УРОВЕНЬ!",
                "Полтысячи уровней — это очень мощно!",
            ),

            600: (
                "💫 600 УРОВЕНЬ!",
                "Ты буквально не собираешься останавливаться!",
            ),

            700: (
                "🚀 700 УРОВЕНЬ!",
                "Твой прогресс уже впечатляет!",
            ),

            800: (
                "⚡ 800 УРОВЕНЬ!",
                "Ещё один огромный рубеж покорён!",
            ),

            900: (
                "💎 900 УРОВЕНЬ!",
                "Ты совсем рядом с тысячным уровнем!",
            ),

            1000: (
                "👑 1000 УРОВЕНЬ!",
                "ЛЕГЕНДАРНЫЙ РЕЗУЛЬТАТ!",
            ),
        }

        if level in special:

            title, description = (
                special[level]
            )

        else:

            title = (
                f"🎉 {level} УРОВЕНЬ!"
            )

            description = (
                "Ты достиг нового большого "
                "рубежа и продолжаешь развиваться!"
            )

        progress = (
            XPSystem.get_progress_from_xp(
                total_xp
            )
        )

        return (
            f"{title}\n\n"

            f"⭐ <b>{user_name}</b>\n\n"

            f"🏆 Ты достиг "
            f"<b>{level}</b> уровня!\n\n"

            f"💎 XP нового уровня: "
            f"<b>{progress.current_level_xp}</b>"
            f" / "
            f"<b>{progress.required_for_next}</b>\n\n"

            f"📈 Всего XP: "
            f"<b>{total_xp}</b>\n\n"

            f"{description}\n\n"

            "🎁 Новый уровень — новый статус!"
        )

    # =====================================================
    # XP TOP
    # =====================================================

    def top_text(
        self,
        limit: int = 10,
    ) -> str:

        db = self._get_db()

        users = db.get_xp_top(
            limit=limit
        )

        if not users:

            return (
                "🏆 <b>ТОП ПО XP</b>\n\n"
                "Пока здесь никого нет."
            )

        lines = [
            "🏆 <b>ТОП ПО XP</b>",
            "",
        ]

        medals = {
            1: "🥇",
            2: "🥈",
            3: "🥉",
        }

        for index, user in enumerate(
            users,
            start=1,
        ):

            xp = int(
                user["xp"] or 0
            )

            level = (
                self.calculate_level(
                    xp
                )
            )

            first_name = (
                str(
                    user["first_name"]
                    or ""
                ).strip()
                or "Пользователь"
            )

            title = self.get_title(
                level
            )

            prefix = medals.get(
                index,
                f"{index}.",
            )

            lines.append(
                f"{prefix} "
                f"<b>{first_name}</b>\n"
                f"   💎 {xp} XP"
                f" • 🏆 {level} ур."
                f" • {title}"
            )

        return "\n".join(
            lines
        )

    # =====================================================
    # DAILY QUESTS
    # =====================================================

    def daily_quests(
        self,
        user_id: int,
    ) -> list[dict]:

        stats = self.get_stats(
            user_id
        )

        message_count = stats.get(
            "message",
            0,
        )

        like_count = stats.get(
            "like",
            0,
        )

        search_count = stats.get(
            "search",
            0,
        )

        return [
            {
                "id": "messages_5",
                "title": "💬 Общение",
                "description": "Отправить 5 сообщений",
                "current": min(
                    message_count,
                    5,
                ),
                "required": 5,
                "reward": 50,
                "completed": (
                    message_count >= 5
                ),
            },

            {
                "id": "likes_3",
                "title": "❤️ Активность",
                "description": "Поставить 3 лайка",
                "current": min(
                    like_count,
                    3,
                ),
                "required": 3,
                "reward": 75,
                "completed": (
                    like_count >= 3
                ),
            },

            {
                "id": "search_5",
                "title": "🔎 Поиск",
                "description": "Посмотреть 5 профилей",
                "current": min(
                    search_count,
                    5,
                ),
                "required": 5,
                "reward": 50,
                "completed": (
                    search_count >= 5
                ),
            },
        ]

    # =====================================================
    # DAILY QUEST TEXT
    # =====================================================

    def daily_quests_text(
        self,
        user_id: int,
    ) -> str:

        quests = self.daily_quests(
            user_id
        )

        lines = [
            "🎯 <b>ЕЖЕДНЕВНЫЕ ЗАДАНИЯ</b>",
            "",
        ]

        for quest in quests:

            status = (
                "✅"
                if quest["completed"]
                else "⏳"
            )

            lines.append(
                f"{status} "
                f"<b>{quest['title']}</b>\n"

                f"   {quest['description']}\n"

                f"   📊 "
                f"{quest['current']}/"
                f"{quest['required']}\n"

                f"   💎 "
                f"+{quest['reward']} XP"
            )

            lines.append("")

        return "\n".join(
            lines
        )

    # =====================================================
    # RESET CACHE
    # =====================================================

    def reset_user_cache(
        self,
        user_id: int,
    ) -> None:

        self._cooldowns = {
            key: value
            for key, value
            in self._cooldowns.items()
            if key[0] != user_id
        }

        self._daily_xp.pop(
            user_id,
            None,
        )

        self._streaks.pop(
            user_id,
            None,
        )

        self._achievements.pop(
            user_id,
            None,
        )

        self._stats.pop(
            user_id,
            None,
        )