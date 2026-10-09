from __future__ import annotations

import argparse
from pathlib import Path

from database import Database


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restore VK-Moderator from a SQLite backup."
    )
    parser.add_argument(
        "--database",
        default="data/bot.db",
        help="Path to the live database (default: data/bot.db).",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Path to a previously created backup.",
    )
    args = parser.parse_args()

    source_path = Path(args.source).expanduser()
    if not source_path.is_file():
        parser.error(f"Backup file does not exist: {source_path}")

    try:
        database = Database(str(Path(args.database).expanduser()))
        safety_copy = database.restore_from(source_path, create_backup=True)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(f"Restore failed: {exc}")

    print("Restore completed.")
    if safety_copy is not None:
        print(f"Previous database preserved at: {safety_copy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
