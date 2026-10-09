import unittest
from unittest.mock import AsyncMock

from start import handle_event


class HandleEventTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispatches_callback_api_nested_message(self):
        router = AsyncMock()
        event = {
            "type": "message_new",
            "object": {
                "message": {
                    "text": "  !правила  ",
                    "peer_id": 2000000001,
                    "from_id": 12345,
                }
            },
        }

        await handle_event(event, router)

        router.dispatch.assert_awaited_once_with(
            peer_id=2000000001,
            user_id=12345,
            text="!правила",
        )

    async def test_keeps_compatibility_with_flat_message_object(self):
        router = AsyncMock()
        event = {
            "type": "message_new",
            "object": {
                "text": "!help",
                "peer_id": 2000000001,
                "from_id": 12345,
            },
        }

        await handle_event(event, router)

        router.dispatch.assert_awaited_once_with(
            peer_id=2000000001,
            user_id=12345,
            text="!help",
        )

    async def test_ignores_non_message_event(self):
        router = AsyncMock()

        await handle_event({"type": "group_join", "object": {}}, router)

        router.dispatch.assert_not_awaited()

    async def test_ignores_missing_message_fields(self):
        router = AsyncMock()

        await handle_event(
            {"type": "message_new", "object": {"message": {"text": "hello"}}},
            router,
        )

        router.dispatch.assert_not_awaited()



    async def test_ignores_non_dictionary_event(self):
        router = AsyncMock()

        await handle_event(None, router)

        router.dispatch.assert_not_awaited()

    async def test_ignores_invalid_message_identifiers(self):
        router = AsyncMock()
        event = {
            "type": "message_new",
            "object": {
                "message": {
                    "text": "!help",
                    "peer_id": "not-a-number",
                    "from_id": 12345,
                }
            },
        }

        await handle_event(event, router)

        router.dispatch.assert_not_awaited()

    async def test_ignores_non_positive_identifiers(self):
        for user_id in (0, -123):
            with self.subTest(user_id=user_id):
                router = AsyncMock()
                event = {
                    "type": "message_new",
                    "object": {
                        "message": {
                            "text": "!help",
                            "peer_id": 2000000001,
                            "from_id": user_id,
                        }
                    },
                }

                await handle_event(event, router)

                router.dispatch.assert_not_awaited()

if __name__ == "__main__":
    unittest.main()
