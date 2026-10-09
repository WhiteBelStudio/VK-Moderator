import unittest

from xp import XPSystem


class XPLevelBoundaryTests(unittest.TestCase):
    def test_level_one_and_negative_xp(self):
        self.assertEqual(XPSystem.xp_for_level(1), 0)
        self.assertEqual(XPSystem.calculate_level(0), 1)
        self.assertEqual(XPSystem.calculate_level(-1), 1)

    def test_exact_threshold_enters_level(self):
        for level in (2, 3, 10, 50, 100):
            with self.subTest(level=level):
                self.assertEqual(
                    XPSystem.calculate_level(XPSystem.xp_for_level(level)),
                    level,
                )

    def test_one_xp_below_threshold_stays_previous_level(self):
        for level in (2, 3, 10, 50, 100):
            with self.subTest(level=level):
                threshold = XPSystem.xp_for_level(level)
                self.assertEqual(XPSystem.calculate_level(threshold - 1), level - 1)

    def test_thresholds_increase(self):
        previous = XPSystem.xp_for_level(1)
        for level in (2, 3, 10, 50, 100, 250, 500, 750, 1000):
            threshold = XPSystem.xp_for_level(level)
            self.assertGreater(threshold, previous)
            previous = threshold

    def test_level_is_capped_at_maximum(self):
        threshold = XPSystem.xp_for_level(XPSystem.MAX_LEVEL)
        self.assertEqual(
            XPSystem.calculate_level(threshold + 1_000_000),
            XPSystem.MAX_LEVEL,
        )

    def test_next_level_threshold_and_cap(self):
        for level in (1, 2, 10, 99):
            with self.subTest(level=level):
                self.assertEqual(
                    XPSystem.next_level_xp(level),
                    XPSystem.xp_for_level(level + 1),
                )
        self.assertEqual(
            XPSystem.next_level_xp(XPSystem.MAX_LEVEL),
            XPSystem.xp_for_level(XPSystem.MAX_LEVEL),
        )


if __name__ == "__main__":
    unittest.main()
