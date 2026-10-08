from __future__ import annotations

import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv


DEFAULT_API_VERSION = "5.199"
DEFAULT_XP_PER_MESSAGE = 1
DEFAULT_XP_PER_LEVEL = 200
DEFAULT_MAX_RP_TEXT = 300

_API_VERSION_RE = re.compile(r"^\d+\.\d+$")


load_dotenv()


def get_int_list(value: str) -> set[int]:
    """Парсит список целых ID, разделённых запятыми."""
    result: set[int] = set()

    for item in str(value or "").split(","):
        item = item.strip()
        if not item:
            continue

        try:
            parsed = int(item)
        except ValueError as exc:
            raise RuntimeError(
                f"ADMIN_IDS содержит некорректный ID: {item!r}"
            ) from exc

        if parsed <= 0:
            raise RuntimeError(
                f"ADMIN_IDS содержит недопустимый ID: {parsed}"
            )

        result.add(parsed)

    return result


def _get_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Не указан {name} в файле .env")
    return value


def _get_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default)).strip()

    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"{name} должен быть целым числом, получено: {raw!r}"
        ) from exc

    if value < minimum:
        raise RuntimeError(
            f"{name} должен быть не меньше {minimum}, получено: {value}"
        )

    return value


@dataclass(frozen=True)
class Config:
    vk_token: str
    group_id: int
    api_version: str
    admin_ids: set[int]
    xp_per_message: int
    xp_per_level: int
    max_rp_text: int


def load_config() -> Config:
    """Загружает и валидирует конфигурацию из окружения."""
    token = _get_required("VK_TOKEN")

    group_id_raw = _get_required("VK_GROUP_ID")
    try:
        group_id = int(group_id_raw)
    except ValueError as exc:
        raise RuntimeError(
            f"VK_GROUP_ID должен быть целым числом, получено: {group_id_raw!r}"
        ) from exc

    if group_id <= 0:
        raise RuntimeError(
            f"VK_GROUP_ID должен быть положительным, получено: {group_id}"
        )

    api_version = os.getenv(
        "VK_API_VERSION",
        DEFAULT_API_VERSION,
    ).strip() or DEFAULT_API_VERSION

    if not _API_VERSION_RE.fullmatch(api_version):
        raise RuntimeError(
            f"VK_API_VERSION имеет неверный формат: {api_version!r}"
        )

    return Config(
        vk_token=token,
        group_id=group_id,
        api_version=api_version,
        admin_ids=get_int_list(os.getenv("ADMIN_IDS", "")),
        xp_per_message=_get_int(
            "XP_PER_MESSAGE",
            DEFAULT_XP_PER_MESSAGE,
            minimum=1,
        ),
        xp_per_level=_get_int(
            "XP_PER_LEVEL",
            DEFAULT_XP_PER_LEVEL,
            minimum=1,
        ),
        max_rp_text=_get_int(
            "MAX_RP_TEXT",
            DEFAULT_MAX_RP_TEXT,
            minimum=20,
        ),
    )
