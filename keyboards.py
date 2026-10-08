from __future__ import annotations

import json
from typing import Any


def callback_button(
    label: str,
    payload: dict[str, Any],
    color: str = "primary",
) -> dict[str, Any]:
    """
    Создание VK callback-кнопки.

    В payload передаются только JSON-совместимые данные.
    Никаких объектов ManiacGame.
    """

    payload_json = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return {
        "action": {
            "type": "callback",
            "label": label,
            "payload": payload_json,
        },
        "color": color,
    }


def make_keyboard(
    rows: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    return {
        "one_time": False,
        "buttons": rows,
    }


def game_payload(
    game_peer_id: int,
    action: str,
    **extra: Any,
) -> dict[str, Any]:
    """
    Формирование callback payload.

    В callback передаём только:
    - game_peer_id
    - action
    - простые значения
    """

    payload = {
        "game_peer_id": int(game_peer_id),
        "action": str(action),
    }

    payload.update(extra)

    return payload


# ==========================================================
# ЛОББИ
# ==========================================================

def lobby_keyboard(game) -> dict[str, Any]:
    """
    Кнопки главного сообщения лобби.

    Это единственная клавиатура, которая отображается
    в общем чате во время набора игроков.
    """

    peer_id = int(game.peer_id)

    return make_keyboard(
        [
            [
                callback_button(
                    "🎮 Войти",
                    game_payload(
                        peer_id,
                        "join",
                    ),
                    "positive",
                ),
                callback_button(
                    "🚪 Выйти",
                    game_payload(
                        peer_id,
                        "leave",
                    ),
                    "negative",
                ),
            ],
            [
                callback_button(
                    "▶️ Начать",
                    game_payload(
                        peer_id,
                        "start",
                    ),
                    "primary",
                ),
                callback_button(
                    "❌ Закрыть",
                    game_payload(
                        peer_id,
                        "stop",
                    ),
                    "negative",
                ),
            ],
        ]
    )


# ==========================================================
# МАНЬЯК
# ==========================================================

def maniac_keyboard(
    game,
    targets,
) -> dict[str, Any]:
    peer_id = int(game.peer_id)

    buttons: list[dict[str, Any]] = []

    for player in targets:
        buttons.append(
            callback_button(
                f"🎯 {player.first_name}",
                game_payload(
                    peer_id,
                    "maniac_target",
                    target_id=int(player.user_id),
                ),
                "negative",
            )
        )

    return make_keyboard(
        split_buttons(buttons)
    )


# ==========================================================
# ШЕРИФ
# ==========================================================

def sheriff_keyboard(
    game,
    targets,
) -> dict[str, Any]:
    peer_id = int(game.peer_id)

    buttons: list[dict[str, Any]] = []

    for player in targets:
        buttons.append(
            callback_button(
                f"🔎 {player.first_name}",
                game_payload(
                    peer_id,
                    "sheriff_check",
                    target_id=int(player.user_id),
                ),
                "primary",
            )
        )

    return make_keyboard(
        split_buttons(buttons)
    )


# ==========================================================
# ДОКТОР
# ==========================================================

def doctor_keyboard(
    game,
    targets,
) -> dict[str, Any]:
    peer_id = int(game.peer_id)

    buttons: list[dict[str, Any]] = []

    for player in targets:
        buttons.append(
            callback_button(
                f"🩺 {player.first_name}",
                game_payload(
                    peer_id,
                    "doctor_protect",
                    target_id=int(player.user_id),
                ),
                "positive",
            )
        )

    return make_keyboard(
        split_buttons(buttons)
    )


# ==========================================================
# ГОЛОСОВАНИЕ
# ==========================================================

def vote_keyboard(
    game,
    targets,
) -> dict[str, Any]:
    peer_id = int(game.peer_id)

    buttons: list[dict[str, Any]] = []

    for player in targets:
        buttons.append(
            callback_button(
                f"🗳 {player.first_name}",
                game_payload(
                    peer_id,
                    "vote",
                    target_id=int(player.user_id),
                ),
                "primary",
            )
        )

    buttons.append(
        callback_button(
            "⏭ Пропустить",
            game_payload(
                peer_id,
                "vote_skip",
            ),
            "secondary",
        )
    )

    return make_keyboard(
        split_buttons(buttons)
    )


# ==========================================================
# HELPERS
# ==========================================================

def split_buttons(
    buttons: list[dict[str, Any]],
    per_row: int = 4,
) -> list[list[dict[str, Any]]]:

    if not buttons:
        return []

    return [
        buttons[index:index + per_row]
        for index in range(
            0,
            len(buttons),
            per_row,
        )
    ]