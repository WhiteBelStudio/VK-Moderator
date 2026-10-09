import os
import unittest
from unittest.mock import AsyncMock, patch

import aiohttp

from vk_api import (
    VKAPIAuthError,
    VKAPIClient,
    VKAPIRequestError,
    VKAPIResponseError,
)


class _InvalidJSONResponse:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def raise_for_status(self):
        return None

    async def json(self, content_type=None):
        raise ValueError("invalid JSON")


class _InvalidJSONSession:
    closed = False

    def __init__(self):
        self.calls = 0

    def post(self, url, data):
        self.calls += 1
        return _InvalidJSONResponse()


class _PayloadResponse(_InvalidJSONResponse):
    def __init__(self, payload):
        self.payload = payload

    async def json(self, content_type=None):
        return self.payload


class _PayloadSession:
    closed = False

    def __init__(self, payload):
        self.payload = payload

    def post(self, url, data):
        return _PayloadResponse(self.payload)


class _RetrySession:
    closed = False

    def __init__(self):
        self.calls = 0

    def post(self, url, data):
        self.calls += 1
        if self.calls == 1:
            raise aiohttp.ClientConnectionError("temporary network failure")
        return _PayloadResponse({"response": [{"id": 1}]})




class VKAPIErrorTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_json_is_normalized_to_request_error(self):
        client = VKAPIClient(token=os.getenv("VK_TEST_TOKEN", "unit-test"), retries=0)
        session = _InvalidJSONSession()
        client._session = session

        with self.assertRaises(VKAPIRequestError):
            await client.call("users.get", user_ids="1")

        self.assertEqual(session.calls, 1)

    async def test_missing_response_remains_response_error(self):
        client = VKAPIClient(token=os.getenv("VK_TEST_TOKEN", "unit-test"), retries=0)
        client._session = _PayloadSession({"unexpected": []})

        with self.assertRaises(VKAPIResponseError):
            await client.call("users.get", user_ids="1")

    async def test_transient_network_error_is_retried(self):
        client = VKAPIClient(token=os.getenv("VK_TEST_TOKEN", "unit-test"), retries=1)
        session = _RetrySession()
        client._session = session

        with patch("vk_api.asyncio.sleep", new_callable=AsyncMock):
            result = await client.call("users.get", user_ids="1")

        self.assertEqual(result, {"response": [{"id": 1}]})
        self.assertEqual(session.calls, 2)

    async def test_authentication_error_is_not_retried_as_transport_error(self):
        client = VKAPIClient(token=os.getenv("VK_TEST_TOKEN", "unit-test"), retries=0)
        client._session = _PayloadSession(
            {"error": {"error_code": 5, "error_msg": "Invalid token"}}
        )

        with self.assertRaises(VKAPIAuthError):
            await client.call("users.get", user_ids="1")


if __name__ == "__main__":
    unittest.main()
