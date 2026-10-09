import os
import unittest
from unittest.mock import patch

from config import load_config


class ConfigValidationTests(unittest.TestCase):
    def test_minimal_valid_configuration_uses_defaults(self):
        with patch.dict(
            os.environ,
            {"VK_TOKEN": "test-token", "VK_GROUP_ID": "12345"},
            clear=True,
        ):
            config = load_config()

        self.assertEqual(config.vk_token, "test-token")
        self.assertEqual(config.group_id, 12345)
        self.assertEqual(config.api_version, "5.199")
        self.assertEqual(config.admin_ids, set())

    def test_missing_token_is_rejected(self):
        with patch.dict(os.environ, {"VK_GROUP_ID": "12345"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "VK_TOKEN"):
                load_config()

    def test_invalid_group_id_is_rejected(self):
        with patch.dict(
            os.environ,
            {"VK_TOKEN": "test-token", "VK_GROUP_ID": "not-a-number"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "VK_GROUP_ID"):
                load_config()

    def test_invalid_admin_ids_are_rejected(self):
        with patch.dict(
            os.environ,
            {
                "VK_TOKEN": "test-token",
                "VK_GROUP_ID": "12345",
                "ADMIN_IDS": "123,not-an-id",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "ADMIN_IDS"):
                load_config()

    def test_non_positive_admin_ids_are_rejected(self):
        with patch.dict(
            os.environ,
            {
                "VK_TOKEN": "test-token",
                "VK_GROUP_ID": "12345",
                "ADMIN_IDS": "0",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "ADMIN_IDS"):
                load_config()


if __name__ == "__main__":
    unittest.main()
