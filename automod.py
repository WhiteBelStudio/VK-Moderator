from __future__ import annotations

import os
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque


@dataclass(slots=True)
class AutoModerationResult:
    violated: bool = False
    reason: str = ""
    notify: bool = True


class AutoModerationSystem:

    def __init__(
        self,
        max_message_length: int = 1500,
        flood_messages: int = 6,
        flood_window: float = 5.0,
        duplicate_limit: int = 3,
        mention_limit: int = 5,
        max_warnings: int = 3,
        forbidden_words: list[str] | None = None,
    ):
        self.max_message_length = max(
            100,
            int(max_message_length),
        )

        self.flood_messages = max(
            2,
            int(flood_messages),
        )

        self.flood_window = max(
            1.0,
            float(flood_window),
        )

        self.duplicate_limit = max(
            2,
            int(duplicate_limit),
        )

        self.mention_limit = max(
            1,
            int(mention_limit),
        )

        self.max_warnings = max(
            1,
            int(max_warnings),
        )

        # Explicit constructor configuration wins; otherwise load a comma-separated
        # list from FORBIDDEN_WORDS. An unset variable means no extra words.
        configured_words = (
            forbidden_words
            if forbidden_words is not None
            else os.getenv("FORBIDDEN_WORDS", "").split(",")
        )
        self.forbidden_words = [
            str(word).casefold().strip()
            for word in configured_words
            if str(word).strip()
        ]

        self._messages: dict[
            int,
            Deque[tuple[float, str]],
        ] = defaultdict(
            lambda: deque(
                maxlen=50
            )
        )

        self._last_violation: dict[
            int,
            float,
        ] = {}

        self.violation_cooldown = 3.0

    # ========================================================
    # REMEMBER
    # ========================================================

    def remember(
        self,
        user_id: int,
        text: str,
    ) -> None:

        try:
            user_id = int(user_id)
        except (
            ValueError,
            TypeError,
        ):
            return

        text = str(
            text or ""
        ).strip()

        if not text:
            return

        now = time.monotonic()

        self._cleanup(
            user_id,
            now,
        )

        self._messages[user_id].append(
            (
                now,
                text,
            )
        )

    # ========================================================
    # CHECK
    # ========================================================

    def check(
        self,
        user_id: int,
        text: str,
    ) -> AutoModerationResult:

        try:
            user_id = int(user_id)
        except (
            ValueError,
            TypeError,
        ):
            return AutoModerationResult()

        text = str(
            text or ""
        ).strip()

        if not text:
            return AutoModerationResult()

        now = time.monotonic()

        self._cleanup(
            user_id,
            now,
        )

        messages = self._messages[user_id]

        # Проверяем нарушение до добавления
        # текущего сообщения в историю.

        # ----------------------------------------------------
        # Длина сообщения
        # ----------------------------------------------------

        if len(text) > self.max_message_length:

            return self._violation(
                user_id,
                "Слишком длинное сообщение",
                now,
            )

        # ----------------------------------------------------
        # Flood
        # ----------------------------------------------------

        recent = [
            item
            for item in messages
            if now - item[0]
            <= self.flood_window
        ]

        if len(recent) >= self.flood_messages - 1:

            return self._violation(
                user_id,
                "Флуд",
                now,
            )

        # ----------------------------------------------------
        # Повтор одинакового сообщения
        # ----------------------------------------------------

        normalized = self._normalize(
            text
        )

        duplicate_count = 0

        for _, old_text in reversed(messages):

            if self._normalize(
                old_text
            ) == normalized:

                duplicate_count += 1

            else:

                break

        if duplicate_count >= (
            self.duplicate_limit - 1
        ):

            return self._violation(
                user_id,
                "Повтор одинакового сообщения",
                now,
            )

        # ----------------------------------------------------
        # Упоминания
        # ----------------------------------------------------

        mentions = len(
            re.findall(
                r"\[id\d+\|",
                text,
                flags=re.IGNORECASE,
            )
        )

        mentions += len(
            re.findall(
                r"@\w+",
                text,
            )
        )

        if mentions >= self.mention_limit:

            return self._violation(
                user_id,
                "Слишком много упоминаний",
                now,
            )

        # ----------------------------------------------------
        # Ссылки
        # ----------------------------------------------------

        links = re.findall(
            r"https?://\S+",
            text,
            flags=re.IGNORECASE,
        )

        if len(links) >= 5:

            return self._violation(
                user_id,
                "Слишком много ссылок",
                now,
            )

        # ----------------------------------------------------
        # CAPS
        # ----------------------------------------------------

        letters = [
            char
            for char in text
            if char.isalpha()
        ]

        if len(letters) >= 10:

            upper_count = sum(
                1
                for char in letters
                if char.isupper()
            )

            upper_percent = (
                upper_count
                / len(letters)
            )

            if upper_percent >= 0.80:

                return self._violation(
                    user_id,
                    "Чрезмерное использование заглавных букв",
                    now,
                )

        # ----------------------------------------------------
        # Повтор символов
        # ----------------------------------------------------

        if re.search(
            r"(.)\1{9,}",
            text,
            flags=re.DOTALL,
        ):

            return self._violation(
                user_id,
                "Чрезмерное повторение символов",
                now,
            )

        # ----------------------------------------------------
        # Запрещённые слова
        # ----------------------------------------------------

        lower_text = text.casefold()

        for word in self.forbidden_words:

            if not word:
                continue

            pattern = (
                r"(?<!\w)"
                + re.escape(word)
                + r"(?!\w)"
            )

            if re.search(
                pattern,
                lower_text,
            ):

                return self._violation(
                    user_id,
                    "Запрещённое слово",
                    now,
                )

        # Сообщение прошло проверки.
        self.remember(
            user_id,
            text,
        )

        return AutoModerationResult()

    # ========================================================
    # VIOLATION
    # ========================================================

    def _violation(
        self,
        user_id: int,
        reason: str,
        now: float,
    ) -> AutoModerationResult:

        last = self._last_violation.get(
            user_id,
            0.0,
        )

        # Не выдаём десятки предупреждений подряд
        # при одном и том же флуде.
        if (
            now - last
            < self.violation_cooldown
        ):

            self.remember(
                user_id,
                "",
            )

            return AutoModerationResult(
                violated=True,
                reason=reason,
                notify=False,
            )

        self._last_violation[
            user_id
        ] = now

        return AutoModerationResult(
            violated=True,
            reason=reason,
        )

    # ========================================================
    # CLEANUP
    # ========================================================

    def _cleanup(
        self,
        user_id: int,
        now: float,
    ) -> None:

        messages = self._messages.get(
            user_id
        )

        if not messages:
            return

        while messages:

            timestamp, _ = messages[0]

            if (
                now - timestamp
                <= max(
                    self.flood_window,
                    60.0,
                )
            ):
                break

            messages.popleft()

    # ========================================================
    # NORMALIZE
    # ========================================================

    @staticmethod
    def _normalize(
        text: str,
    ) -> str:

        text = str(
            text or ""
        ).casefold()

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self) -> None:

        self._messages.clear()
        self._last_violation.clear()


# Обратная совместимость.
# Можно импортировать как AutoModeration
# или как AutoModerationSystem.

AutoModeration = AutoModerationSystem