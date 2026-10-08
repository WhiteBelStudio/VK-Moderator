from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def get_int_list(value: str) -> set[int]:
    result: set[int] = set()

    if not value:
        return result

    for item in value.split(","):
        item = item.strip()

        if not item:
            continue

        try:
            result.add(int(item))
        except ValueError:
            continue

    return result


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
    token = os.getenv(
        "VK_TOKEN",
        "",
    ).strip()

    if not token:
        raise RuntimeError(
            "Не указан VK_TOKEN в файле .env"
        )

    group_id_raw = os.getenv(
        "VK_GROUP_ID",
        "",
    ).strip()

    if not group_id_raw:
        raise RuntimeError(
            "Не указан VK_GROUP_ID в файле .env"
        )

    try:
        group_id = int(group_id_raw)
    except ValueError as exc:
        raise RuntimeError(
            "VK_GROUP_ID должен быть числом"
        ) from exc

    api_version = os.getenv(
        "VK_API_VERSION",
        "5.199",
    ).strip()

    if not api_version:
        api_version = "5.199"

    try:
        xp_per_message = int(
            os.getenv(
                "XP_PER_MESSAGE",
                "1",
            )
        )
    except ValueError:
        xp_per_message = 1

    try:
        xp_per_level = int(
            os.getenv(
                "XP_PER_LEVEL",
                "200",
            )
        )
    except ValueError:
        xp_per_level = 200

    try:
        max_rp_text = int(
            os.getenv(
                "MAX_RP_TEXT",
                "300",
            )
        )
    except ValueError:
        max_rp_text = 300

    return Config(
        vk_token=token,
        group_id=group_id,
        api_version=api_version,
        admin_ids=get_int_list(
            os.getenv(
                "ADMIN_IDS",
                "",
            )
        ),
        xp_per_message=max(
            1,
            xp_per_message,
        ),
        xp_per_level=max(
            1,
            xp_per_level,
        ),
        max_rp_text=max(
            20,
            max_rp_text,
        ),
    )