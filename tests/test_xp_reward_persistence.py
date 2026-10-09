import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import Database
from xp import XPSystem


class XPRewardPersistenceTests(unittest.TestCase):
    def test_add_xp_persists_total_xp_and_level(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(str(Path(directory) / "bot.db"))
            xp = XPSystem(database)

            result = xp.add_xp(user_id=12345, amount=25, action="test")

            user = database.get_user(12345)
            self.assertEqual(result["new_xp"], 25)
            self.assertEqual(user["xp"], 25)
            self.assertEqual(user["level"], 1)

    def test_non_positive_reward_does_not_change_persisted_xp(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(str(Path(directory) / "bot.db"))
            database.update_xp(user_id=12345, xp=25, level=1)
            xp = XPSystem(database)

            result = xp.add_xp(user_id=12345, amount=0, action="test")

            user = database.get_user(12345)
            self.assertEqual(result["xp_added"], 0)
            self.assertEqual(user["xp"], 25)
            self.assertEqual(user["level"], 1)

    def test_existing_v1_database_is_migrated_without_losing_xp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.db"
            migration_dir = Path(__file__).resolve().parents[1] / "migrations"
            connection = sqlite3.connect(path)
            connection.execute(
                "CREATE TABLE schema_migrations "
                "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            connection.executescript(
                (migration_dir / "001_initial.sql").read_text(encoding="utf-8")
            )
            connection.execute("INSERT INTO schema_migrations(version) VALUES (1)")
            connection.execute(
                "INSERT INTO users(user_id, first_name, xp) VALUES (12345, 'Legacy', 500)"
            )
            connection.commit()
            connection.close()

            database = Database(str(path))
            user = database.get_user(12345)

            self.assertEqual(user["xp"], 500)
            self.assertEqual(user["level"], 1)

            with database.connect() as connection:
                version = connection.execute(
                    "SELECT MAX(version) FROM schema_migrations"
                ).fetchone()[0]
            self.assertEqual(version, 2)


if __name__ == "__main__":
    unittest.main()
