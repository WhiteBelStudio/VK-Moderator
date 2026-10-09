import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from database import Database
from moderation import ModerationModule


class ModerationModuleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db = Database(str(Path(self.temp_dir.name) / "bot.db"))
        self.vk = AsyncMock()
        self.module = ModerationModule(
            vk=self.vk,
            db=self.db,
            group_id=99,
            admin_ids={1},
        )

    async def test_non_moderator_cannot_ban(self):
        handled = await self.module.handle_message(
            peer_id=2000000001,
            user_id=2,
            text="!бан @id123 spam",
        )

        self.assertTrue(handled)
        self.vk.call.assert_not_awaited()
        self.vk.send_message.assert_awaited_once()
        self.assertEqual(self.db.get_warning_count(123), 0)

    async def test_admin_ban_uses_group_api_and_audit_log(self):
        await self.module.handle_message(
            peer_id=2000000001,
            user_id=1,
            text="!бан @id123 repeated spam",
        )

        self.vk.call.assert_awaited_once_with(
            "groups.ban",
            group_id=99,
            owner_id=123,
            comment="repeated spam",
            comment_visible=0,
        )
        with self.db.connect() as connection:
            action = connection.execute(
                "SELECT actor_id, target_id, action, reason FROM moderation_actions"
            ).fetchone()
        self.assertEqual(tuple(action), (1, 123, "ban", "repeated spam"))

    async def test_warning_is_persisted(self):
        await self.module.handle_message(
            peer_id=2000000001,
            user_id=1,
            text="!пред @id123 flood",
        )

        self.assertEqual(self.db.get_warning_count(123), 1)
        self.vk.send_message.assert_awaited_once()

    async def test_mute_and_unmute_are_persisted(self):
        await self.module.handle_message(
            peer_id=2000000001,
            user_id=1,
            text="!мут @id123 15 flood",
        )
        self.assertTrue(self.db.is_muted(123))

        await self.module.handle_message(
            peer_id=2000000001,
            user_id=1,
            text="!размут @id123",
        )
        self.assertFalse(self.db.is_muted(123))

    async def test_only_configured_admin_can_assign_roles(self):
        await self.module.handle_message(
            peer_id=2000000001,
            user_id=1,
            text="!роль @id123 moderator",
        )
        self.assertEqual(self.db.get_role(123), "moderator")

        await self.module.handle_message(
            peer_id=2000000001,
            user_id=123,
            text="!пред @id456 spam",
        )
        self.assertEqual(self.db.get_warning_count(456), 1)

    async def test_kick_requires_chat_and_uses_chat_id(self):
        await self.module.handle_message(
            peer_id=2000000001,
            user_id=1,
            text="!кик @id123 spam",
        )

        self.vk.call.assert_awaited_once_with(
            "messages.removeChatUser",
            chat_id=1,
            user_id=123,
            group_id=99,
        )


if __name__ == "__main__":
    unittest.main()
