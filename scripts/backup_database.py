from __future__ import annotations

import argparse
from pathlib import Path

from scripts.sqlite_maintenance import backup_sqlite


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a consistent SQLite backup of VK-Moderator."
    )
    parser.add_argument(
        "--database",
        default="data/bot.db",
        help="Path to the live database (default: data/bot.db).",
    )
    parser.add_argument(
        "--destination",
        required=True,
        help="Path for the backup SQLite file.",
    )
    args = parser.parse_args()

    database_path = Path(args.database).expanduser()
    if not database_path.is_file():
        parser.error(f"Database file does not exist: {database_path}")

    try:
        backup_path = backup_sqlite(database_path, args.destination)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(f"Backup failed: {exc}")

    print(f"Backup created: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
