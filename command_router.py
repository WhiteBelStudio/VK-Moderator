from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger("vk-moderator.command-router")

CommandHandler = Callable[[int, int, str], Awaitable[bool]]


class CommandRouter:
    """Единая точка маршрутизации текстовых команд VK-бота."""

    def __init__(self, vk: Any) -> None:
        self.vk = vk
        self._handlers: dict[str, CommandHandler] = {}
        self._modules: list[Any] = []

    @staticmethod
    def parse(text: str) -> tuple[str, str]:
        raw = str(text or "").strip()
        if not raw:
            return "", ""
        parts = raw.split(maxsplit=1)
        command = parts[0].casefold()
        args = parts[1].strip() if len(parts) == 2 else ""
        return command, args

    def register(self, command: str, handler: CommandHandler) -> None:
        normalized = str(command).strip().casefold()
        if not normalized.startswith("!"):
            normalized = f"!{normalized}"
        if not normalized:
            raise ValueError("Command cannot be empty.")
        self._handlers[normalized] = handler

    def register_module(self, module: Any) -> None:
        """Подключает модуль с COMMANDS и handle_message()."""
        self._modules.append(module)
        commands = getattr(module, "COMMANDS", set())
        handler = getattr(module, "handle_message", None)
        if callable(handler):
            for command in commands:
                self.register(command, handler)

    async def send(self, peer_id: int, message: str) -> None:
        await self.vk.call(
            "messages.send",
            peer_id=int(peer_id),
            random_id=0,
            message=str(message),
        )

    async def dispatch(
        self,
        peer_id: int,
        user_id: int,
        text: str,
        first_name: str | None = None,
    ) -> bool:
        command, args = self.parse(text)
        if not command:
            return False

        handler = self._handlers.get(command)
        if handler is None:
            for module in self._modules:
                module_handler = getattr(module, "handle_message", None)
                if not callable(module_handler):
                    continue
                try:
                    handled = await module_handler(
                        int(peer_id),
                        int(user_id),
                        str(text),
                        first_name,
                    )
                except (RuntimeError, ValueError, TypeError, KeyError):
                    logger.exception("Command module failed: %s", command)
                    continue
                if handled:
                    return True
            return False

        try:
            return bool(
                await handler(
                    int(peer_id),
                    int(user_id),
                    str(text),
                    first_name,
                )
            )
        except TypeError:
            try:
                return bool(
                    await handler(
                        int(peer_id),
                        int(user_id),
                        str(text),
                    )
                )
            except (RuntimeError, ValueError, TypeError, KeyError):
                logger.exception("Command handler failed: %s", command)
                await self.send(
                    peer_id,
                    "❌ При обработке команды произошла ошибка.",
                )
                return True
        except (RuntimeError, ValueError, TypeError, KeyError):
            logger.exception("Command handler failed: %s", command)
            await self.send(
                peer_id,
                "❌ При обработке команды произошла ошибка.",
            )
            return True
