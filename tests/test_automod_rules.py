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


    def test_flood_is_detected_after_configured_window_count(self):
        system = AutoModerationSystem(flood_messages=3, flood_window=5.0)
        system.remember(201, "first")
        system.remember(201, "second")

        result = system.check(201, "third")

        self.assertTrue(result.violated)
        self.assertEqual(result.reason, "Флуд")

    def test_repeated_message_is_detected(self):
        system = AutoModerationSystem(duplicate_limit=3)
        system.remember(202, "same message")
        system.remember(202, "same message")

        result = system.check(202, "same message")

        self.assertTrue(result.violated)
        self.assertEqual(result.reason, "Повтор одинакового сообщения")

    def test_mention_limit_is_enforced(self):
        system = AutoModerationSystem(mention_limit=3)

        result = system.check(203, "@alice @bob @charlie")

        self.assertTrue(result.violated)
        self.assertEqual(result.reason, "Слишком много упоминаний")

    def test_link_limit_is_enforced(self):
        system = AutoModerationSystem()
        message = " ".join(f"https://example.com/{index}" for index in range(5))

        result = system.check(204, message)

        self.assertTrue(result.violated)
        self.assertEqual(result.reason, "Слишком много ссылок")

    def test_excessive_caps_is_detected(self):
        system = AutoModerationSystem()

        result = system.check(205, "THIS IS VERY LOUD")

        self.assertTrue(result.violated)
        self.assertEqual(result.reason, "Чрезмерное использование заглавных букв")

    def test_repeated_characters_are_detected(self):
        system = AutoModerationSystem()

        result = system.check(206, "x" * 10)

        self.assertTrue(result.violated)
        self.assertEqual(result.reason, "Чрезмерное повторение символов")

    def test_warning_cooldown_does_not_disable_enforcement(self):
        system = AutoModerationSystem(max_message_length=100)

        first = system.check(207, "x" * 101)
        second = system.check(207, "y" * 101)

        self.assertTrue(first.violated)
        self.assertTrue(first.notify)
        self.assertTrue(second.violated)
        self.assertFalse(second.notify)

if __name__ == "__main__":
    unittest.main()
