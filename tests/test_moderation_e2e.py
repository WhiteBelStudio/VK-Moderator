import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from automod import AutoModerationSystem
from command_router import CommandRouter
from database import Database
from moderation import ModerationModule
from start import handle_event
from xp import XPSystem


class _FakeVK:
    def __init__(self):
        self.call = AsyncMock()
        self.send_message = AsyncMock()


class ModerationEndToEndTests(unittest.IsolatedAsyncioTestCase):
    async def test_incoming_admin_warning_updates_database_and_audit_log(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(str(Path(directory) / "bot.db"))
            vk = _FakeVK()
            router = CommandRouter(vk)
            router.register_module(
                ModerationModule(vk=vk, db=db, group_id=99, admin_ids={1})
            )

            event = {
                "type": "message_new",
                "event_id": "moderation-e2e-1",
                "object": {
                    "message": {
                        "id": 1001,
                        "text": "!пред @id123 flood",
                        "peer_id": 2000000001,
                        "from_id": 1,
                    }
                },
            }

            await handle_event(
                event,
                router,
                AutoModerationSystem(),
                db,
                {1},
                XPSystem(db, message_xp=1),
            )

            self.assertEqual(db.get_warning_count(123), 1)
            with db.connect() as connection:
                action = connection.execute(
                    "SELECT actor_id, target_id, action, reason FROM moderation_actions"
                ).fetchone()
            self.assertEqual(tuple(action), (1, 123, "warn", "flood"))
            vk.send_message.assert_awaited_once()
            vk.call.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
