import os
import unittest
from unittest.mock import patch

from automod import AutoModerationSystem
from rp import RPSystem


class ForbiddenWordsConfigTests(unittest.TestCase):
    def test_automod_reads_environment_list(self):
        with patch.dict(os.environ, {"FORBIDDEN_WORDS": "badword, forbidden"}):
            system = AutoModerationSystem()
        self.assertEqual(system.forbidden_words, ["badword", "forbidden"])

    def test_automod_explicit_list_overrides_environment(self):
        with patch.dict(os.environ, {"FORBIDDEN_WORDS": "environmentword"}):
            system = AutoModerationSystem(forbidden_words=["CustomWord"])
        self.assertEqual(system.forbidden_words, ["customword"])

    def test_rp_reads_environment_list(self):
        with patch.dict(os.environ, {"FORBIDDEN_WORDS": "badword, forbidden"}):
            system = RPSystem(db=None, vk=None)
        self.assertEqual(system.forbidden_words, ("badword", "forbidden"))
        self.assertTrue(system.is_forbidden("this contains BADWORD"))
        self.assertFalse(system.is_forbidden("ordinary text"))

    def test_rp_explicit_list_overrides_environment(self):
        with patch.dict(os.environ, {"FORBIDDEN_WORDS": "environmentword"}):
            system = RPSystem(db=None, vk=None, forbidden_words=["CustomWord"])
        self.assertEqual(system.forbidden_words, ("customword",))


if __name__ == "__main__":
    unittest.main()
