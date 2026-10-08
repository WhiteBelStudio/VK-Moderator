from __future__ import annotations

from typing import Any

import aiohttp


class VKAPIError(RuntimeError):
    """Ошибка взаимодействия с VK API."""


class VKAPIClient:
    """Асинхронный минимальный клиент VK API."""

    def __init__(
        self,
        token: str,
        api_version: str = "5.199",
        timeout: float = 15.0,
    ) -> None:
        token = str(token).strip()
        if not token:
            raise ValueError("VK token cannot be empty.")

        self.token = token
        self.api_version = str(api_version).strip() or "5.199"
        self.timeout = aiohttp.ClientTimeout(total=float(timeout))
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> "VKAPIClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    async def call(self, method: str, **params: Any) -> dict[str, Any]:
        if not method or "." not in method:
            raise ValueError("VK method must look like 'users.get'.")

        await self.start()
        assert self._session is not None

        request_params = {
            **params,
            "access_token": self.token,
            "v": self.api_version,
        }

        url = f"https://api.vk.com/method/{method}"

        try:
            async with self._session.post(url, data=request_params) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise VKAPIError(
                f"VK API request failed: {method}"
            ) from exc

        if not isinstance(payload, dict):
            raise VKAPIError("VK API returned an invalid response.")

        error = payload.get("error")
        if error:
            code = error.get("error_code", "unknown")
            message = error.get("error_msg", "Unknown VK API error")
            raise VKAPIError(f"VK API error {code}: {message}")

        if "response" not in payload:
            raise VKAPIError(f"VK API response is missing for {method}.")

        return payload

    async def get_group(self, group_id: int) -> dict[str, Any]:
        """Получить данные сообщества и проверить доступ токена."""
        result = await self.call(
            "groups.getById",
            group_id=int(group_id),
        )
        response = result["response"]

        if isinstance(response, dict):
            groups = response.get("groups", [])
        else:
            groups = response

        if not groups:
            raise VKAPIError(
                f"VK community {group_id} was not found or is inaccessible."
            )

        return groups[0]
