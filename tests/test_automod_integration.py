import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from automod import AutoModerationSystem
from database import Database
from start import handle_event


class AutoModerationIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_violation_is_deleted_warned_and_not_dispatched(self):
        router = AsyncMock()
        automod = AutoModerationSystem(max_message_length=100)
        event = {
            "type": "message_new",
            "object": {
                "message": {
                    "id": 543,
                    "text": "x" * 101,
                    "peer_id": 2000000001,
                    "from_id": 12345,
                }
            },
        }

        await handle_event(event, router, automod)

        router.vk.call.assert_awaited_once_with(
            "messages.delete",
            message_ids="543",
            delete_for_all=1,
        )
        router.send.assert_awaited_once_with(
            2000000001,
            "⚠️ Сообщение отклонено: Слишком длинное сообщение.",
        )
        router.dispatch.assert_not_awaited()

    async def test_valid_message_continues_to_router(self):
        router = AsyncMock()
        automod = AutoModerationSystem()
        event = {
            "type": "message_new",
            "object": {
                "message": {
                    "id": 544,
                    "text": "!help",
                    "peer_id": 2000000001,
                    "from_id": 12346,
                }
            },
        }

        await handle_event(event, router, automod)

        router.dispatch.assert_awaited_once_with(
            peer_id=2000000001,
            user_id=12346,
            text="!help",
        )
        router.send.assert_not_awaited()


    async def test_active_mute_deletes_message_before_router_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(str(Path(directory) / "bot.db"))
            database.set_mute(12347, 10, "test", 1)
            router = AsyncMock()
            event = {
                "type": "message_new",
                "object": {
                    "message": {
                        "id": 545,
                        "text": "!help",
                        "peer_id": 2000000001,
                        "from_id": 12347,
                    }
                },
            }

            await handle_event(event, router, db=database)

        router.vk.call.assert_awaited_once_with(
            "messages.delete",
            message_ids="545",
            delete_for_all=1,
        )
        router.dispatch.assert_not_awaited()

    async def test_warning_cooldown_still_deletes_later_violations(self):
        router = AsyncMock()
        automod = AutoModerationSystem(max_message_length=100)

        def event(message_id, user_id):
            return {
                "type": "message_new",
                "object": {
                    "message": {
                        "id": message_id,
                        "text": "x" * 101,
                        "peer_id": 2000000001,
                        "from_id": user_id,
                    }
                },
            }

        await handle_event(event(546, 12348), router, automod)
        await handle_event(event(547, 12348), router, automod)

        self.assertEqual(router.vk.call.await_count, 2)
        self.assertEqual(router.send.await_count, 1)
        router.dispatch.assert_not_awaited()

    async def test_configured_admin_bypasses_automod(self):
        router = AsyncMock()
        automod = Mock()
        event = {
            "type": "message_new",
            "object": {
                "message": {
                    "id": 548,
                    "text": "x" * 101,
                    "peer_id": 2000000001,
                    "from_id": 12349,
                }
            },
        }

        await handle_event(event, router, automod, admin_ids={12349})

        automod.check.assert_not_called()
        router.vk.call.assert_not_awaited()
        router.send.assert_not_awaited()
        router.dispatch.assert_awaited_once_with(
            peer_id=2000000001,
            user_id=12349,
            text="x" * 101,
        )

if __name__ == "__main__":
    unittest.main()
