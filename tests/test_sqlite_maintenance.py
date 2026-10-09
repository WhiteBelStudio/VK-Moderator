import tempfile
import unittest
from pathlib import Path

from database import Database
from marriage import MarriageDatabase
from scripts.sqlite_maintenance import backup_sqlite, restore_sqlite, validate_database


class SQLiteMaintenanceTests(unittest.TestCase):
    def test_main_database_backup_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            live_path = root / "bot.db"
            db = Database(str(live_path))
            db.update_xp(12345, 100, 1)
            backup = backup_sqlite(live_path, root / "backups" / "bot-backup.sqlite3")

            db.update_xp(12345, 999, 3)
            safety_copy = restore_sqlite(backup, live_path)

            self.assertIsNotNone(safety_copy)
            self.assertTrue(safety_copy.is_file())
            self.assertEqual(Database(str(live_path)).get_user(12345)["xp"], 100)
            self.assertEqual(validate_database(backup), "main")

    def test_marriage_database_backup_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            live_path = root / "marriage.db"
            marriage_db = MarriageDatabase(db_path=live_path)
            backup = backup_sqlite(live_path, root / "backups" / "marriage-backup.sqlite3")

            marriage_db.create_marriage(12345, 12346)
            safety_copy = restore_sqlite(backup, live_path)

            self.assertIsNotNone(safety_copy)
            self.assertTrue(safety_copy.is_file())
            self.assertIsNone(MarriageDatabase(db_path=live_path).get_marriage(12345))
            self.assertEqual(validate_database(backup), "marriage")

    def test_restore_rejects_mismatched_database_kinds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            main_path = root / "bot.db"
            Database(str(main_path))
            marriage_path = root / "marriage.db"
            MarriageDatabase(db_path=marriage_path)

            with self.assertRaises(ValueError):
                restore_sqlite(main_path, marriage_path)


if __name__ == "__main__":
    unittest.main()
