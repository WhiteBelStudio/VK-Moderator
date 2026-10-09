from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

import aiohttp

from vk_api import VKAPIClient, VKAPIError


class VKLongPoll:
    """Асинхронный клиент VK Long Poll API для событий сообщества."""

    def __init__(
        self,
        api: VKAPIClient,
        group_id: int,
        wait: int = 25,
    ) -> None:
        self.api = api
        self.group_id = int(group_id)
        self.wait = max(1, min(int(wait), 60))
        self._running = False

    async def get_server(self) -> dict[str, Any]:
        result = await self.api.call(
            "groups.getLongPollServer",
            group_id=self.group_id,
        )
        response = result.get("response")
        if not isinstance(response, dict):
            raise VKAPIError("VK Long Poll server response is invalid.")

        for key in ("key", "server", "ts"):
            if key not in response:
                raise VKAPIError(
                    f"VK Long Poll response is missing '{key}'."
                )

        return response

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        """Получать события, корректно обрабатывая коды failed Long Poll."""
        self._running = True
        server = await self.get_server()

        while self._running:
            params = {
                "act": "a_check",
                "key": server["key"],
                "wait": self.wait,
                "ts": server["ts"],
            }

            try:
                # get_server() starts the shared API session before this loop.
                session = self.api._session
                if session is None or session.closed:
                    await self.api.start()
                    session = self.api._session
                if session is None:
                    raise VKAPIError("VK Long Poll HTTP session is unavailable.")

                async with session.post(
                    server["server"],
                    params=params,
                ) as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                if not self._running:
                    break
                raise VKAPIError("VK Long Poll connection failed.") from exc
            except ValueError as exc:
                raise VKAPIError("VK Long Poll returned invalid JSON.") from exc

            if not isinstance(payload, dict):
                raise VKAPIError("VK Long Poll returned invalid JSON.")

            failed = payload.get("failed")
            if failed is not None:
                if failed == 1:
                    # The server reports a newer timestamp; update it and poll again.
                    if "ts" not in payload:
                        raise VKAPIError(
                            "VK Long Poll failed=1 response is missing 'ts'."
                        )
                    server["ts"] = payload["ts"]
                    continue

                if failed in (2, 3):
                    # The key/server is no longer valid; request fresh credentials.
                    server = await self.get_server()
                    continue

                if failed == 4:
                    raise VKAPIError(
                        "VK Long Poll API version is unsupported; "
                        "check VK_API_VERSION."
                    )

                raise VKAPIError(
                    f"VK Long Poll returned unknown failure code {failed!r}."
                )

            if "ts" not in payload:
                raise VKAPIError("VK Long Poll response is missing 'ts'.")

            server["ts"] = payload["ts"]

            updates = payload.get("updates", [])
            if not isinstance(updates, list):
                raise VKAPIError("VK Long Poll 'updates' field is not a list.")

            for event in updates:
                if isinstance(event, dict):
                    yield event

    def stop(self) -> None:
        self._running = False


async def run_long_poll(
    api: VKAPIClient,
    group_id: int,
    handler: Any,
) -> None:
    """Запустить Long Poll и передавать каждое событие обработчику."""
    poll = VKLongPoll(api, group_id)

    try:
        async for event in poll.events():
            await handler(event)
    finally:
        poll.stop()
