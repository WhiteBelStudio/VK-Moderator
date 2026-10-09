from __future__ import annotations

import logging
import re
import sqlite3
from typing import Any

from database import Database
from vk_api import VKAPIError

logger = logging.getLogger("vk-moderator.moderation")

_MENTION_RE = re.compile(r"\[id(\d+)\|[^\]]*\]|@?id(\d+)", re.IGNORECASE)

_ALIASES = {
    "/бан": "!бан",
    "/разбан": "!разбан",
    "/кик": "!кик",
    "/пред": "!пред",
    "/снятьпред": "!снятьпред",
    "/мут": "!мут",
    "/размут": "!размут",
    "/роль": "!роль",
    "!ban": "!бан",
    "!unban": "!разбан",
    "!kick": "!кик",
    "!warn": "!пред",
    "!unwarn": "!снятьпред",
    "!mute": "!мут",
    "!unmute": "!размут",
    "!role": "!роль",
}


class ModerationModule:
    """Admin-only moderation commands with persistent warnings, mutes and audit log."""

    COMMANDS = {
        "!бан",
        "!разбан",
        "!кик",
        "!пред",
        "!снятьпред",
        "!мут",
        "!размут",
        "!роль",
    }

    def __init__(
        self,
        vk: Any,
        db: Database,
        group_id: int,
        admin_ids: set[int] | None = None,
    ) -> None:
        self.vk = vk
        self.db = db
        self.group_id = int(group_id)
        self.admin_ids = {int(value) for value in (admin_ids or set())}

    @staticmethod
    def _parse_target(args: str) -> tuple[int | None, str]:
        match = _MENTION_RE.search(args)
        if match is None:
            return None, args.strip()
        raw_id = match.group(1) or match.group(2)
        remaining = (args[:match.start()] + " " + args[match.end():]).strip()
        return int(raw_id), remaining

    async def _reply(self, peer_id: int, message: str) -> None:
        await self.vk.send_message(peer_id=int(peer_id), message=message)

    def _is_moderator(self, user_id: int) -> bool:
        return (
            int(user_id) in self.admin_ids
            or self.db.get_role(int(user_id)) in {"moderator", "admin"}
        )

    async def handle_message(
        self,
        peer_id: int,
        user_id: int,
        text: str,
        first_name: str | None = None,
    ) -> bool:
        raw = str(text or "").strip()
        if not raw:
            return False

        parts = raw.split(maxsplit=1)
        command = parts[0].casefold()
        command = _ALIASES.get(command, command)
        if command not in self.COMMANDS:
            return False

        if not self._is_moderator(user_id):
            await self._reply(peer_id, "⛔ Недостаточно прав для команды модерации.")
            return True

        args = parts[1] if len(parts) > 1 else ""
        target_id, remaining = self._parse_target(args)
        if target_id is None or target_id <= 0:
            await self._reply(
                peer_id,
                "Использование: команда @id123 [причина].",
            )
            return True
        if target_id == int(user_id):
            await self._reply(peer_id, "Нельзя применять это действие к самому себе.")
            return True

        reason = remaining.strip() or "Причина не указана"

        try:
            if command == "!бан":
                await self.vk.call(
                    "groups.ban",
                    group_id=self.group_id,
                    owner_id=target_id,
                    comment=reason[:500],
                    comment_visible=0,
                )
                self.db.log_moderation_action(user_id, target_id, "ban", reason)
                await self._reply(peer_id, f"🔨 Пользователь id{target_id} заблокирован в сообществе.")

            elif command == "!разбан":
                await self.vk.call(
                    "groups.unban",
                    group_id=self.group_id,
                    owner_id=target_id,
                )
                self.db.log_moderation_action(user_id, target_id, "unban", reason)
                await self._reply(peer_id, f"✅ Блокировка id{target_id} снята.")

            elif command == "!кик":
                if int(peer_id) < 2_000_000_000:
                    await self._reply(peer_id, "Команда кика работает только внутри беседы VK.")
                    return True
                await self.vk.call(
                    "messages.removeChatUser",
                    chat_id=int(peer_id) - 2_000_000_000,
                    user_id=target_id,
                    group_id=self.group_id,
                )
                self.db.log_moderation_action(user_id, target_id, "kick", reason)
                await self._reply(peer_id, f"👢 Пользователь id{target_id} исключён из беседы.")

            elif command == "!пред":
                count = self.db.add_warning(target_id, reason)
                self.db.log_moderation_action(user_id, target_id, "warn", reason)
                await self._reply(
                    peer_id,
                    f"⚠️ Предупреждение выдано id{target_id}. Всего предупреждений: {count}.",
                )

            elif command == "!снятьпред":
                before = self.db.get_warning_count(target_id)
                if before == 0:
                    await self._reply(peer_id, f"У пользователя id{target_id} нет предупреждений.")
                    return True
                count = self.db.remove_warning(target_id)
                self.db.log_moderation_action(user_id, target_id, "unwarn", reason)
                await self._reply(
                    peer_id,
                    f"✅ Одно предупреждение снято с id{target_id}. Осталось: {count}.",
                )

            elif command == "!мут":
                mute_parts = remaining.split(maxsplit=1)
                if not mute_parts or not mute_parts[0].isdigit():
                    await self._reply(peer_id, "Использование: !мут @id123 минуты [причина].")
                    return True
                duration = int(mute_parts[0])
                mute_reason = mute_parts[1].strip() if len(mute_parts) > 1 else "Причина не указана"
                self.db.set_mute(target_id, duration, mute_reason, user_id)
                self.db.log_moderation_action(
                    user_id,
                    target_id,
                    "mute",
                    f"{duration} минут: {mute_reason}",
                )
                await self._reply(
                    peer_id,
                    f"🔇 Пользователь id{target_id} ограничен на {duration} мин.",
                )

            elif command == "!размут":
                removed = self.db.remove_mute(target_id)
                if not removed:
                    await self._reply(peer_id, f"У пользователя id{target_id} нет активного мута.")
                    return True
                self.db.log_moderation_action(user_id, target_id, "unmute", reason)
                await self._reply(peer_id, f"🔊 Ограничение с id{target_id} снято.")

            elif command == "!роль":
                if int(user_id) not in self.admin_ids:
                    await self._reply(peer_id, "⛔ Назначать роли могут только ID из ADMIN_IDS.")
                    return True
                role_parts = remaining.split(maxsplit=1)
                role = role_parts[0].casefold() if role_parts else ""
                if role not in {"user", "moderator", "admin"}:
                    await self._reply(peer_id, "Использование: !роль @id123 user|moderator|admin.")
                    return True
                self.db.set_role(target_id, role)
                self.db.log_moderation_action(user_id, target_id, "role", role)
                await self._reply(peer_id, f"✅ Для id{target_id} установлена роль: {role}.")

        except VKAPIError:
            logger.exception(
                "VK moderation API action failed: command=%s actor=%s target=%s",
                command,
                user_id,
                target_id,
            )
            await self._reply(peer_id, "❌ VK не выполнил действие. Проверьте права сообщества и журнал.")
        except (ValueError, TypeError, KeyError, sqlite3.Error) as exc:
            logger.exception(
                "Invalid moderation action: command=%s actor=%s target=%s",
                command,
                user_id,
                target_id,
            )
            await self._reply(peer_id, f"❌ Не удалось выполнить действие: {exc}")

        return True
