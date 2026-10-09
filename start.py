from __future__ import annotations

import asyncio
import logging

from command_router import CommandRouter
from automod import AutoModerationSystem
from config import load_config
from database import Database
from event_deduplication import EventDeduplicator
from logging_config import configure_logging
from marriage import MarriageModule
from moderation import ModerationModule
from profile import ProfileSystem
from rules import RulesSystem
from xp import XPSystem
from vk_api import VKAPIClient, VKAPIError
from vk_longpoll import run_long_poll

logger = logging.getLogger("vk-moderator")

_event_deduplicator = EventDeduplicator()


async def handle_event(
    event: dict,
    router: CommandRouter,
    automod: AutoModerationSystem | None = None,
    db: Database | None = None,
    admin_ids: set[int] | None = None,
    xp_system: XPSystem | None = None,
) -> None:
    """Передаёт сообщения VK в единый маршрутизатор команд."""
    if not isinstance(event, dict):
        logger.warning("Ignoring malformed VK event: expected a dictionary.")
        return

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

    try:
        normalized_peer_id = int(peer_id)
        normalized_user_id = int(user_id)
    except (TypeError, ValueError):
        logger.warning("Ignoring malformed VK message event: invalid peer_id/from_id.")
        return

    if _event_deduplicator.is_duplicate(event):
        logger.info("Ignoring duplicate VK event_id=%s.", event.get("event_id"))
        return

    if db is not None and db.is_muted(normalized_user_id):
        message_id = obj.get("id")
        if message_id is not None:
            try:
                await router.vk.call(
                    "messages.delete",
                    message_ids=str(int(message_id)),
                    delete_for_all=1,
                )
            except (VKAPIError, TypeError, ValueError):
                logger.exception(
                    "Could not delete message from muted user_id=%s.",
                    normalized_user_id,
                )
        logger.info("Ignored message from muted user_id=%s.", normalized_user_id)
        return

    privileged_users = {int(value) for value in (admin_ids or set())}
    if db is not None and db.get_role(normalized_user_id) in {"moderator", "admin"}:
        privileged_users.add(normalized_user_id)

    if automod is not None and normalized_user_id not in privileged_users:
        result = automod.check(normalized_user_id, text)
        if result.violated:
            message_id = obj.get("id")
            if message_id is not None:
                try:
                    await router.vk.call(
                        "messages.delete",
                        message_ids=str(int(message_id)),
                        delete_for_all=1,
                    )
                except (VKAPIError, TypeError, ValueError):
                    logger.exception(
                        "AutoMod could not delete violating message_id=%s.",
                        message_id,
                    )

            if result.notify:
                try:
                    await router.send(
                        normalized_peer_id,
                        f"⚠️ Сообщение отклонено: {result.reason}.",
                    )
                except VKAPIError:
                    logger.exception(
                        "AutoMod could not notify peer_id=%s.",
                        normalized_peer_id,
                    )
            else:
                logger.debug(
                    "AutoMod warning suppressed by cooldown for user_id=%s.",
                    normalized_user_id,
                )
            return

    if xp_system is not None:
        try:
            xp_system.process_message(normalized_user_id)
        except Exception:
            logger.exception(
                "Could not award message XP to user_id=%s.",
                normalized_user_id,
            )

    await router.dispatch(
        peer_id=normalized_peer_id,
        user_id=normalized_user_id,
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
        automod = AutoModerationSystem()
        xp_system = XPSystem(db)
        moderation = ModerationModule(
            vk=vk,
            db=db,
            group_id=config.group_id,
            admin_ids=config.admin_ids,
        )
        router.register_module(moderation)
        marriage = MarriageModule(vk, core_db=db)
        router.register_module(marriage)
        router.register_module(
            ProfileSystem(
                bot=vk,
                db=db,
                config=config,
                marriage=marriage,
            )
        )
        router.register_module(RulesSystem(vk))

        async def dispatch_event(event: dict) -> None:
            await handle_event(event, router, automod, db, config.admin_ids, xp_system)

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
