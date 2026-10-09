import tempfile
import unittest
from pathlib import Path

from database import Database


class DatabaseUserTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db = Database(str(Path(self.temp_dir.name) / "users.db"))

    def test_ensure_user_creates_and_updates_profile(self):
        self.db.ensure_user(12345, "First", "Name")
        first = self.db.get_user(12345)
        self.assertIsNotNone(first)
        self.assertEqual(first["first_name"], "First")
        self.assertEqual(first["last_name"], "Name")

        self.db.ensure_user(12345, "Updated", "Profile")
        updated = self.db.get_user(12345)
        self.assertEqual(updated["first_name"], "Updated")
        self.assertEqual(updated["last_name"], "Profile")
        self.assertEqual(updated["user_id"], 12345)

    def test_missing_user_returns_none(self):
        self.assertIsNone(self.db.get_user(987654321))

    def test_xp_top_is_sorted_and_limited(self):
        self.db.update_xp(101, 50, 1)
        self.db.update_xp(102, 150, 1)
        self.db.update_xp(103, 100, 1)

        top = self.db.get_xp_top(limit=2)

        self.assertEqual([row["user_id"] for row in top], [102, 103])
        self.assertEqual([row["xp"] for row in top], [150, 100])


if __name__ == "__main__":
    unittest.main()
