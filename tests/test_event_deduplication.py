import unittest
from unittest.mock import AsyncMock, patch

import start
from event_deduplication import EventDeduplicator


class EventDeduplicatorTests(unittest.TestCase):
    def test_duplicate_ids_are_detected(self):
        deduplicator = EventDeduplicator()
        event = {"event_id": "abc"}

        self.assertFalse(deduplicator.is_duplicate(event))
        self.assertTrue(deduplicator.is_duplicate(event))

    def test_cache_is_bounded(self):
        deduplicator = EventDeduplicator(max_entries=2)
        self.assertFalse(deduplicator.is_duplicate({"event_id": "a"}))
        self.assertFalse(deduplicator.is_duplicate({"event_id": "b"}))
        self.assertFalse(deduplicator.is_duplicate({"event_id": "c"}))
        # The oldest entry is evicted when the configured limit is exceeded.
        self.assertFalse(deduplicator.is_duplicate({"event_id": "a"}))

    def test_events_without_ids_are_not_deduplicated(self):
        deduplicator = EventDeduplicator()
        self.assertFalse(deduplicator.is_duplicate({"type": "message_new"}))
        self.assertFalse(deduplicator.is_duplicate({"type": "message_new"}))


class EventDeduplicationIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_duplicate_message_is_dispatched_only_once(self):
        router = AsyncMock()
        event = {
            "type": "message_new",
            "event_id": "unique-event-123",
            "object": {
                "message": {
                    "text": "!help",
                    "peer_id": 2000000001,
                    "from_id": 12345,
                }
            },
        }

        with patch.object(start, "_event_deduplicator", EventDeduplicator()):
            await start.handle_event(event, router)
            await start.handle_event(event, router)

        router.dispatch.assert_awaited_once_with(
            peer_id=2000000001,
            user_id=12345,
            text="!help",
        )


if __name__ == "__main__":
    unittest.main()
