import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from automod import AutoModerationSystem
from database import Database
from start import handle_event
from xp import XPSystem


class XPMessageIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_message_awards_xp_and_persists_it(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(str(Path(directory) / "bot.db"))
            xp_system = XPSystem(database)
            router = AsyncMock()
            event = {
                "type": "message_new",
                "object": {
                    "message": {
                        "id": 549,
                        "text": "hello there",
                        "peer_id": 2000000001,
                        "from_id": 12350,
                    }
                },
            }

            await handle_event(
                event,
                router,
                AutoModerationSystem(),
                database,
                xp_system=xp_system,
            )

            user = database.get_user(12350)
            self.assertGreaterEqual(user["xp"], XPSystem.MESSAGE_XP)
            self.assertEqual(user["level"], XPSystem.calculate_level(user["xp"]))
            router.dispatch.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
