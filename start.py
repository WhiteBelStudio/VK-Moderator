from __future__ import annotations

import asyncio
import logging

from command_router import CommandRouter
from config import load_config
from database import Database
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

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

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
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
