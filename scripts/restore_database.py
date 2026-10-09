from __future__ import annotations

import argparse
from pathlib import Path

from scripts.sqlite_maintenance import restore_sqlite


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
        safety_copy = restore_sqlite(source_path, Path(args.database).expanduser())
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(f"Restore failed: {exc}")

    print("Restore completed.")
    if safety_copy is not None:
        print(f"Previous database preserved at: {safety_copy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
