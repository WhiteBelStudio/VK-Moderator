from __future__ import annotations

import asyncio
import logging

from command_router import CommandRouter
from config import load_config
from database import Database
from logging_config import configure_logging
from marriage import MarriageModule
from rules import RulesSystem
from vk_api import VKAPIClient, VKAPIError
from vk_longpoll import run_long_poll

logger = logging.getLogger("vk-moderator")


async def handle_event(
    event: dict,
    router: CommandRouter,
) -> None:
    """Передаёт сообщения VK в единый маршрутизатор команд."""
    if event.get("type") != "message_new":
        return

    obj = event.get("object") or {}
    if not isinstance(obj, dict):
        return

    # VK Callback API wraps the message in object.message. Some Long Poll
    # versions and test fixtures provide the message fields directly in object.
    nested_message = obj.get("message")
    if isinstance(nested_message, dict):
        obj = nested_message

    text = str(obj.get("text") or "").strip()
    peer_id = obj.get("peer_id")
    user_id = obj.get("from_id")

    if not text or peer_id is None or user_id is None:
        return

    await router.dispatch(
        peer_id=int(peer_id),
        user_id=int(user_id),
        text=text,
    )


async def async_main() -> None:
    config = load_config()
    db = Database()

    async with VKAPIClient(
        token=config.vk_token,
        api_version=config.api_version,
    ) as vk:
        group = await vk.get_group(config.group_id)
        logger.info(
            "VK API connected: community=%s, api=%s.",
            group.get("name", f"ID {config.group_id}"),
            config.api_version,
        )

        router = CommandRouter(vk)
        router.register_module(MarriageModule(vk, core_db=db))
        router.register_module(RulesSystem(vk))

        async def dispatch_event(event: dict) -> None:
            await handle_event(event, router)

        while True:
            try:
                await run_long_poll(
                    vk,
                    config.group_id,
                    dispatch_event,
                )
            except VKAPIError:
                logger.exception("VK Long Poll stopped; retrying in 3 seconds.")
                await asyncio.sleep(3)


def main() -> None:
    configure_logging()
    logger.info("Starting VK-Moderator.")
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user.")
    except Exception:
        logger.exception("Fatal application error.")
        raise


if __name__ == "__main__":
    main()
