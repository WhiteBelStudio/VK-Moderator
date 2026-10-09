import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

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

if __name__ == "__main__":
    unittest.main()
