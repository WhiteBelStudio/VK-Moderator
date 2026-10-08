from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILE = LOG_DIR / "bot.log"
DEFAULT_LOG_LEVEL = "INFO"
MAX_LOG_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3


def configure_logging() -> None:
    """Настраивает единое production-логирование бота."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    level_name = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).strip().upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        raise RuntimeError(
            f"LOG_LEVEL имеет неверное значение: {level_name!r}. "
            "Допустимые значения: DEBUG, INFO, WARNING, ERROR, CRITICAL."
        )

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    root.addHandler(console)
    root.addHandler(file_handler)

    logging.captureWarnings(True)


def get_logger(name: str) -> logging.Logger:
    """Возвращает именованный логгер проекта."""
    return logging.getLogger(name)
