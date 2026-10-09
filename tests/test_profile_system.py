import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from command_router import CommandRouter
from database import Database
from profile import ProfileSystem
from xp import XPSystem


class _FakeBot:
    def __init__(self):
        self.send_message = AsyncMock()


class ProfileSystemTests(unittest.IsolatedAsyncioTestCase):
    async def test_profile_command_is_registered_and_sends_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(str(Path(directory) / "bot.db"))
            db.ensure_user(12345, "Example", "User")
            db.update_xp(12345, 500, XPSystem.calculate_level(500))
            bot = _FakeBot()
            config = SimpleNamespace(admin_ids=set())
            profile = ProfileSystem(bot=bot, db=db, config=config)
            router = CommandRouter(bot)
            router.register_module(profile)

            handled = await router.dispatch(
                peer_id=2000000001,
                user_id=12345,
                text="!профиль",
            )

            self.assertTrue(handled)
            bot.send_message.assert_awaited_once()
            args = bot.send_message.await_args.kwargs
            self.assertEqual(args["peer_id"], 2000000001)
            self.assertIn("ПРОФИЛЬ", args["message"])
            self.assertIn("Example User", args["message"])

    def test_profile_progress_uses_shared_xp_thresholds(self):
        xp = 500
        expected = XPSystem.get_progress_from_xp(xp)
        actual = ProfileSystem.calculate_xp_progress(xp)

        self.assertEqual(actual["level"], expected.level)
        self.assertEqual(actual["current_xp"], expected.current_level_xp)
        self.assertEqual(actual["level_xp"], expected.required_for_next)
        self.assertEqual(actual["next_level_xp"], expected.remaining_xp)
        self.assertEqual(actual["percent"], expected.percent)

    async def test_slash_profile_command_is_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(str(Path(directory) / "bot.db"))
            db.ensure_user(12345, "Example", "User")
            bot = _FakeBot()
            profile = ProfileSystem(
                bot=bot,
                db=db,
                config=SimpleNamespace(admin_ids=set()),
            )

            handled = await profile.handle_message(
                peer_id=2000000001,
                user_id=12345,
                text="/профиль",
            )

            self.assertTrue(handled)
            bot.send_message.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
