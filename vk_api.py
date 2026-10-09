from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp


class VKAPIError(RuntimeError):
    """Базовая ошибка VK API."""


class VKAPIRequestError(VKAPIError):
    """Сетевая ошибка, таймаут или HTTP-ошибка."""


class VKAPIResponseError(VKAPIError):
    """Некорректный ответ VK."""


class VKAPIMethodError(VKAPIError):
    """VK вернул ошибку конкретного метода."""


class VKAPIRateLimitError(VKAPIMethodError):
    """Превышен лимит запросов VK."""


class VKAPIAuthError(VKAPIMethodError):
    """Ошибка авторизации или токена."""


@dataclass(frozen=True)
class VKMethodErrorInfo:
    code: int | None
    message: str


class VKAPIClient:
    """Асинхронный VK API клиент с обработкой ошибок и повторами."""

    def __init__(
        self,
        token: str,
        api_version: str = "5.199",
        timeout: float = 15.0,
        retries: int = 2,
    ) -> None:
        token = str(token).strip()
        if not token:
            raise ValueError("VK token cannot be empty.")

        self.token = token
        self.api_version = str(api_version).strip() or "5.199"
        self.timeout = aiohttp.ClientTimeout(total=float(timeout))
        self.retries = max(0, int(retries))
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

    @staticmethod
    def _method_error(error: Any) -> VKMethodErrorInfo:
        if not isinstance(error, dict):
            return VKMethodErrorInfo(None, "Unknown VK API error.")

        raw_code = error.get("error_code")
        try:
            code = int(raw_code) if raw_code is not None else None
        except (TypeError, ValueError):
            code = None

        return VKMethodErrorInfo(
            code=code,
            message=str(error.get("error_msg") or "Unknown VK API error."),
        )

    @staticmethod
    def _raise_method_error(info: VKMethodErrorInfo) -> None:
        if info.code in {5, 27}:
            raise VKAPIAuthError(
                f"VK API error {info.code}: {info.message}"
            )

        if info.code in {6, 9}:
            raise VKAPIRateLimitError(
                f"VK API error {info.code}: {info.message}"
            )

        raise VKAPIMethodError(
            f"VK API error "
            f"{info.code if info.code is not None else 'unknown'}: "
            f"{info.message}"
        )

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
        last_error: Exception | None = None

        for attempt in range(self.retries + 1):
            try:
                async with self._session.post(
                    url,
                    data=request_params,
                ) as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)

                if not isinstance(payload, dict):
                    raise VKAPIResponseError(
                        f"VK API returned invalid JSON for {method}."
                    )

                error = payload.get("error")
                if error is not None:
                    self._raise_method_error(
                        self._method_error(error)
                    )

                if "response" not in payload:
                    raise VKAPIResponseError(
                        f"VK API response is missing for {method}."
                    )

                return payload

            except VKAPIRateLimitError as exc:
                last_error = exc
                if attempt < self.retries:
                    # VK rate limits are temporary; keep retries bounded.
                    await asyncio.sleep(min(1 + (2 ** attempt), 10))
                    continue
                raise VKAPIRequestError(
                    f"VK rate limit persisted after {self.retries + 1} attempts: {method}"
                ) from exc
            except (VKAPIMethodError, VKAPIResponseError):
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
                # Invalid JSON responses are transient transport/protocol failures too.
                last_error = exc

                if attempt < self.retries:
                    await asyncio.sleep(min(2 ** attempt, 5))
                    continue

                raise VKAPIRequestError(
                    f"VK API request failed after "
                    f"{self.retries + 1} attempts: {method}"
                ) from exc

        raise VKAPIRequestError(
            f"VK API request failed: {method}"
        ) from last_error

    async def send_message(self, peer_id: int, message: str, random_id: int = 0) -> int:
        result = await self.call(
            "messages.send",
            peer_id=int(peer_id),
            random_id=int(random_id),
            message=str(message),
        )
        return int(result["response"])

    async def get_group(self, group_id: int) -> dict[str, Any]:
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
            raise VKAPIResponseError(
                f"VK community {group_id} was not found or is inaccessible."
            )

        return groups[0]
