import unittest

from automod import AutoModerationSystem


class AutoModerationRuleTests(unittest.TestCase):
    def test_forbidden_words_are_case_insensitive(self):
        system = AutoModerationSystem(forbidden_words=["badword"])

        result = system.check(101, "This contains BADWORD.")

        self.assertTrue(result.violated)
        self.assertEqual(result.reason, "Запрещённое слово")

    def test_forbidden_words_match_whole_words_not_substrings(self):
        system = AutoModerationSystem(forbidden_words=["badword"])

        result = system.check(102, "This contains badwordish.")

        self.assertFalse(result.violated)

    def test_empty_text_is_ignored(self):
        system = AutoModerationSystem()

        result = system.check(103, "   ")

        self.assertFalse(result.violated)
        self.assertEqual(result.reason, "")

    def test_long_message_is_flagged(self):
        system = AutoModerationSystem(max_message_length=100)

        result = system.check(104, "x" * 101)

        self.assertTrue(result.violated)
        self.assertEqual(result.reason, "Слишком длинное сообщение")


if __name__ == "__main__":
    unittest.main()
