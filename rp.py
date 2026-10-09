import logging
import os
import re
from html import escape

logger = logging.getLogger("vk-moderator.rp")


class RPSystem:
    """
    RP-система для действий между участниками чата.

    Автор сообщения = исполнитель.
    Упомянутый пользователь = цель действия.
    """

    def __init__(
        self,
        db,
        vk,
        max_text: int = 300,
        forbidden_words: list[str] | tuple[str, ...] | None = None,
    ):
        self.db = db
        self.vk = vk
        self.max_text = max(1, int(max_text))

        self.actions = {
            "обнять": {
                "emoji": "🫂",
                "templates": [
                    "{actor} обнял {target}"
                ],
            },
            "обними": {
                "emoji": "🫂",
                "templates": [
                    "{actor} обнял {target}"
                ],
            },
            "дать пять": {
                "emoji": "🙌",
                "templates": [
                    "{actor} дал пять {target}"
                ],
            },
            "дай пять": {
                "emoji": "🙌",
                "templates": [
                    "{actor} дал пять {target}"
                ],
            },
            "пожать руку": {
                "emoji": "🤝",
                "templates": [
                    "{actor} пожал руку {target}"
                ],
            },
            "пожми руку": {
                "emoji": "🤝",
                "templates": [
                    "{actor} пожал руку {target}"
                ],
            },
            "поздороваться": {
                "emoji": "👋",
                "templates": [
                    "{actor} поздоровался с {target}"
                ],
            },
            "поприветствовать": {
                "emoji": "👋",
                "templates": [
                    "{actor} поприветствовал {target}"
                ],
            },
            "помахать": {
                "emoji": "👋",
                "templates": [
                    "{actor} помахал {target}"
                ],
            },
            "помахать рукой": {
                "emoji": "👋",
                "templates": [
                    "{actor} помахал рукой {target}"
                ],
            },
            "подмигнуть": {
                "emoji": "😉",
                "templates": [
                    "{actor} подмигнул {target}"
                ],
            },
            "улыбнуться": {
                "emoji": "🙂",
                "templates": [
                    "{actor} улыбнулся {target}"
                ],
            },
            "похлопать": {
                "emoji": "👏",
                "templates": [
                    "{actor} похлопал {target}"
                ],
            },
            "похлопать по плечу": {
                "emoji": "👏",
                "templates": [
                    "{actor} похлопал по плечу {target}"
                ],
            },
            "поддержать": {
                "emoji": "💙",
                "templates": [
                    "{actor} поддержал {target}"
                ],
            },
            "поблагодарить": {
                "emoji": "🙏",
                "templates": [
                    "{actor} поблагодарил {target}"
                ],
            },
            "извиниться": {
                "emoji": "🙏",
                "templates": [
                    "{actor} извинился перед {target}"
                ],
            },
            "пнуть": {
                "emoji": "😤",
                "templates": [
                    "{actor} пнул {target}"
                ],
            },
            "толкнуть": {
                "emoji": "😤",
                "templates": [
                    "{actor} толкнул {target}"
                ],
            },
            "пощекотать": {
                "emoji": "😂",
                "templates": [
                    "{actor} пощекотал {target}"
                ],
            },
            "похвалить": {
                "emoji": "⭐",
                "templates": [
                    "{actor} похвалил {target}"
                ],
            },
            "пожелать удачи": {
                "emoji": "🍀",
                "templates": [
                    "{actor} пожелал удачи {target}"
                ],
            },
            "пожелать успехов": {
                "emoji": "🍀",
                "templates": [
                    "{actor} пожелал успехов {target}"
                ],
            },
        }

        default_forbidden_words = (
            "секс",
            "трах",
            "трахнул",
            "трахнула",
            "изнасил",
            "минет",
            "порно",
            "интим",
            "голый",
            "голая",
            "обнажил",
            "обнажила",
        )
        env_words = os.getenv("FORBIDDEN_WORDS", "").strip()
        configured_words = (
            forbidden_words
            if forbidden_words is not None
            else (
                env_words.split(",")
                if env_words
                else default_forbidden_words
            )
        )
        self.forbidden_words = tuple(
            str(word).casefold().strip()
            for word in configured_words
            if str(word).strip()
        )

    @staticmethod
    def extract_target(
        text: str,
    ) -> tuple[int | None, str | None]:

        match = re.search(
            r"\[(?:id|club)(\d+)\|([^\]]+)\]",
            text,
            re.IGNORECASE,
        )

        if not match:
            return None, None

        try:
            user_id = int(match.group(1))
        except (ValueError, TypeError):
            return None, None

        name = match.group(2).strip()

        return user_id, name

    @staticmethod
    def remove_target_mention(
        text: str,
    ) -> str:

        text = re.sub(
            r"\[(?:id|club)\d+\|[^\]]+\]",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    def is_forbidden(
        self,
        text: str,
    ) -> bool:

        lowered = text.casefold()

        return any(
            word in lowered
            for word in self.forbidden_words
        )

    async def get_user_name(
        self,
        user_id: int,
        fallback: str = "Пользователь",
    ) -> str:

        try:
            user = self.db.get_user(user_id)

            if user:
                first_name = str(
                    user["first_name"] or ""
                ).strip()

                if first_name:
                    return first_name

        except Exception:
            logger.exception("RP operation failed.")

        try:
            vk_user = await self.vk.get_user(user_id)

            if vk_user:
                first_name = str(
                    vk_user.get("first_name")
                    or ""
                ).strip()

                if first_name:
                    return first_name

        except Exception:
            logger.exception("RP operation failed.")

        return fallback

    @staticmethod
    def mention(
        user_id: int,
        name: str,
    ) -> str:

        safe_name = escape(
            str(name).strip()
            or "Пользователь"
        )

        return (
            f"[id{int(user_id)}|"
            f"{safe_name}]"
        )

    def build_message(
        self,
        action_text: str,
        actor_mention: str,
        target_mention: str,
    ) -> str | None:

        normalized = (
            action_text
            .casefold()
            .strip()
        )

        action = self.actions.get(normalized)

        if not action:
            return None

        template = action["templates"][0]

        text = template.format(
            actor=actor_mention,
            target=target_mention,
        )

        return f"{action['emoji']} {text}"

    def get_actions_text(self) -> str:
        return (
            "🎭 RP-ДЕЙСТВИЯ\n\n"
            "🫂 Обнять\n"
            "🙌 Дать пять\n"
            "🤝 Пожать руку\n"
            "👋 Поздороваться\n"
            "👋 Помахать\n"
            "😉 Подмигнуть\n"
            "🙂 Улыбнуться\n"
            "👏 Похлопать\n"
            "👏 Похлопать по плечу\n"
            "💙 Поддержать\n"
            "🙏 Поблагодарить\n"
            "🙏 Извиниться\n"
            "😤 Пнуть\n"
            "😤 Толкнуть\n"
            "😂 Пощекотать\n"
            "⭐ Похвалить\n"
            "🍀 Пожелать удачи\n"
            "🍀 Пожелать успехов\n\n"
            "💡 Пример:\n"
            "Обнять [id123|Имя]"
        )

    async def process(
        self,
        peer_id: int,
        sender_id: int,
        text: str,
    ) -> bool:

        text = str(text or "").strip()

        if not text:
            return False

        if len(text) > self.max_text:
            return False

        target_id, target_name_from_message = (
            self.extract_target(text)
        )

        if not target_id:
            return False

        action_text = self.remove_target_mention(text)

        if not action_text:
            return False

        normalized = (
            action_text
            .casefold()
            .strip()
        )

        if normalized not in self.actions:
            return False

        if self.is_forbidden(action_text):
            await self._send(
                peer_id,
                "⛔ Это RP-действие недоступно.",
            )
            return True

        if int(target_id) == int(sender_id):
            await self._send(
                peer_id,
                "😄 Нельзя использовать RP-действие на самого себя.",
            )
            return True

        actor_name = await self.get_user_name(
            sender_id,
            "Пользователь",
        )

        target_name = await self.get_user_name(
            target_id,
            target_name_from_message
            or "Пользователь",
        )

        actor_mention = self.mention(
            sender_id,
            actor_name,
        )

        target_mention = self.mention(
            target_id,
            target_name,
        )

        result = self.build_message(
            action_text=action_text,
            actor_mention=actor_mention,
            target_mention=target_mention,
        )

        if not result:
            return False

        try:
            self.db.add_rp_action(
                actor_id=sender_id,
                target_id=target_id,
                action=action_text,
            )
        except Exception:
            logger.exception("RP operation failed.")

        await self._send(
            peer_id,
            result,
        )

        return True

    async def handle_message(
        self,
        peer_id: int,
        user_id: int,
        text: str,
    ) -> bool:

        return await self.process(
            peer_id=peer_id,
            sender_id=user_id,
            text=text,
        )

    async def _send(
        self,
        peer_id: int,
        text: str,
    ):

        try:
            await self.vk.send_message(
                peer_id=peer_id,
                message=text,
                random_id=0,
            )

        except TypeError:
            try:
                await self.vk.send_message(
                    peer_id=peer_id,
                    message=text,
                )
            except Exception:
                logger.exception("RP operation failed.")

        except Exception:
            logger.exception("RP operation failed.")