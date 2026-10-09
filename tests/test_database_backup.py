import tempfile
import unittest
from pathlib import Path

from database import Database


class DatabaseBackupTests(unittest.TestCase):
    def test_backup_and_restore_preserve_data_and_create_safety_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = Database(str(root / "live.sqlite3"))
            db.ensure_user(12345, "Backup", "Test")
            db.update_xp(12345, 100, 1)

            backup = db.backup_to(root / "backups" / "backup.sqlite3")
            db.update_xp(12345, 999, 3)

            safety_copy = db.restore_from(backup)

            self.assertIsNotNone(safety_copy)
            self.assertTrue(safety_copy.is_file())
            user = db.get_user(12345)
            self.assertEqual(user["xp"], 100)
            self.assertEqual(user["first_name"], "Backup")

    def test_backup_rejects_live_database_as_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "live.sqlite3"
            db = Database(str(path))

            with self.assertRaises(ValueError):
                db.backup_to(path)

    def test_restore_rejects_unknown_database_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = Database(str(root / "live.sqlite3"))
            invalid = root / "not-a-database.sqlite3"
            invalid.write_text("not sqlite", encoding="utf-8")

            with self.assertRaises(ValueError):
                db.restore_from(invalid)


if __name__ == "__main__":
    unittest.main()
