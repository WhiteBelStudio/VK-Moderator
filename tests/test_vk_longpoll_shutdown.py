import unittest
from unittest.mock import patch

from vk_longpoll import run_long_poll


class _FakePoll:
    def __init__(self, api, group_id):
        self.stopped = False

    async def events(self):
        yield {"type": "message_new", "object": {}}

    def stop(self):
        self.stopped = True


class LongPollShutdownTests(unittest.IsolatedAsyncioTestCase):
    async def test_poll_is_stopped_when_handler_raises(self):
        poll = _FakePoll(None, 1)

        async def failing_handler(event):
            raise RuntimeError("handler failure")

        with patch("vk_longpoll.VKLongPoll", return_value=poll):
            with self.assertRaisesRegex(RuntimeError, "handler failure"):
                await run_long_poll(object(), 1, failing_handler)

        self.assertTrue(poll.stopped)


if __name__ == "__main__":
    unittest.main()
