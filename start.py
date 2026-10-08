from __future__ import annotations

import asyncio
import logging

from config import load_config
from vk_api import VKAPIClient, VKAPIError
from vk_longpoll import run_long_poll

logger = logging.getLogger("vk-moderator")


async def handle_event(event: dict) -> None:
    """Базовый обработчик событий; бизнес-команды подключаются далее."""
    event_type = event.get("type", "unknown")
    logger.debug("VK event received: %s", event_type)


async def async_main() -> None:
    config = load_config()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

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

        while True:
            try:
                await run_long_poll(
                    vk,
                    config.group_id,
                    handle_event,
                )
            except VKAPIError:
                logger.exception("VK Long Poll stopped; retrying in 3 seconds.")
                await asyncio.sleep(3)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
