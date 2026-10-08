from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable


logger = logging.getLogger(
    "VKBot.ManiacGame"
)


class Role(str, Enum):
    MANIAC = "maniac"
    SHERIFF = "sheriff"
    DOCTOR = "doctor"
    CIVILIAN = "civilian"


class Phase(str, Enum):
    LOBBY = "lobby"
    NIGHT = "night"
    DAY = "day"
    VOTING = "voting"
    FINISHED = "finished"


@dataclass
class Player:
    user_id: int
    first_name: str

    role: Role | None = None

    alive: bool = True

    night_target: int | None = None
    sheriff_target: int | None = None
    doctor_target: int | None = None

    vote_target: int | None = None

    left_lobby: bool = False

    votes_received: int = 0


@dataclass
class GameResult:
    winner: str
    winner_text: str


SendMessage = Callable[
    [int, str, dict | None],
    Awaitable[int | None],
]

EditMessage = Callable[
    [int, int, str, dict | None],
    Awaitable,
]

DeleteMessage = Callable[
    [int, int],
    Awaitable,
]

PinMessage = Callable[
    [int, int],
    Awaitable,
]

UnpinMessage = Callable[
    [int, int],
    Awaitable,
]

SendPrivate = Callable[
    [int, str, "ManiacGame | None", dict | None],
    Awaitable,
]

SaveStats = Callable[
    [Player, bool],
    Awaitable,
]


class ManiacGame:
    MIN_PLAYERS = 4
    MAX_PLAYERS = 16

    NIGHT_TIME = 45
    DAY_TIME = 60
    VOTING_TIME = 45

    RESULT_DELETE_DELAY = 10

    def __init__(
        self,
        peer_id: int,
        creator_id: int,
        creator_name: str,
        send_message: SendMessage,
        edit_message: EditMessage,
        delete_message: DeleteMessage,
        pin_message: PinMessage,
        unpin_message: UnpinMessage,
        send_private: SendPrivate,
        save_stats: SaveStats,
    ):
        self.peer_id = int(peer_id)
        self.creator_id = int(creator_id)

        self.send_message = send_message
        self.edit_message = edit_message
        self.delete_message = delete_message
        self.pin_message = pin_message
        self.unpin_message = unpin_message
        self.send_private = send_private
        self.save_stats = save_stats

        self.phase = Phase.LOBBY

        self.players: dict[int, Player] = {}

        self.left_players: set[int] = set()

        self.lobby_message_id: int | None = None

        self.closed = False
        self.started = False

        self.task: asyncio.Task | None = None

        self.result: GameResult | None = None

        self.round_number = 0

        self._lock = asyncio.Lock()
        self._finish_started = False

        self.add_player(
            creator_id,
            creator_name,
        )

    @property
    def player_count(self) -> int:
        return len(self.players)

    @property
    def alive_count(self) -> int:
        return sum(
            1
            for player in self.players.values()
            if player.alive
        )

    @property
    def dead_count(self) -> int:
        return (
            self.player_count
            - self.alive_count
        )

    @property
    def maniac(self) -> Player | None:
        return self.find_role(
            Role.MANIAC
        )

    @property
    def sheriff(self) -> Player | None:
        return self.find_role(
            Role.SHERIFF
        )

    @property
    def doctor(self) -> Player | None:
        return self.find_role(
            Role.DOCTOR
        )

    def add_player(
        self,
        user_id: int,
        first_name: str,
    ) -> tuple[bool, str]:

        user_id = int(user_id)

        if self.closed:
            return (
                False,
                "❌ Игра уже закрыта.",
            )

        if self.phase != Phase.LOBBY:
            return (
                False,
                "❌ Игра уже началась.",
            )

        if user_id in self.left_players:
            return (
                False,
                "❌ Вы уже покинули это лобби.",
            )

        if user_id in self.players:
            return (
                False,
                "ℹ️ Вы уже участвуете в игре.",
            )

        if (
            len(self.players)
            >= self.MAX_PLAYERS
        ):
            return (
                False,
                "❌ Лобби заполнено.",
            )

        self.players[user_id] = Player(
            user_id=user_id,
            first_name=(
                first_name.strip()
                if first_name
                else "Игрок"
            ),
        )

        return (
            True,
            "✅ Вы вошли в игру.",
        )

    def remove_player(
        self,
        user_id: int,
    ) -> tuple[bool, str]:

        user_id = int(user_id)

        if self.phase != Phase.LOBBY:
            return (
                False,
                "❌ Во время игры выйти нельзя.",
            )

        if user_id == self.creator_id:
            return (
                False,
                "❌ Создатель игры не может выйти.",
            )

        player = self.players.get(
            user_id
        )

        if player is None:
            return (
                False,
                "❌ Вы не участвуете в игре.",
            )

        player.left_lobby = True

        self.players.pop(
            user_id,
            None,
        )

        self.left_players.add(
            user_id
        )

        return (
            True,
            "✅ Вы покинули лобби.",
        )

    def can_start(self) -> tuple[bool, str]:
        if self.closed:
            return (
                False,
                "❌ Игра закрыта.",
            )

        if self.phase != Phase.LOBBY:
            return (
                False,
                "❌ Игра уже началась.",
            )

        if (
            len(self.players)
            < self.MIN_PLAYERS
        ):
            return (
                False,
                (
                    "❌ Для старта нужно минимум "
                    f"{self.MIN_PLAYERS} игрока."
                ),
            )

        return True, "OK"

    async def start(self) -> tuple[bool, str]:
        async with self._lock:
            allowed, reason = (
                self.can_start()
            )

            if not allowed:
                return False, reason

            self.started = True
            self.phase = Phase.NIGHT
            self.round_number = 1

            self.assign_roles()

            await self.update_lobby_message()

            await self.send_roles()

            await self.send_message(
                self.peer_id,
                (
                    "🎲 МАНЬЯК НАЧИНАЕТСЯ\n\n"
                    f"👥 Игроков: {self.player_count}\n"
                    f"❤️ Живых: {self.alive_count}\n\n"
                    "🌙 Наступает первая ночь.\n"
                    "Роли отправлены игрокам в ЛС.\n\n"
                    f"⏱ На ночь: {self.NIGHT_TIME} секунд."
                ),
                None,
            )

            self.task = asyncio.create_task(
                self.game_loop()
            )

            return (
                True,
                "✅ Игра началась.",
            )

    def assign_roles(self):
        player_ids = list(
            self.players.keys()
        )

        random.shuffle(player_ids)

        for player in self.players.values():
            player.role = Role.CIVILIAN
            player.alive = True
            player.night_target = None
            player.sheriff_target = None
            player.doctor_target = None
            player.vote_target = None
            player.votes_received = 0

        if len(player_ids) >= 4:
            self.players[
                player_ids[0]
            ].role = Role.MANIAC

            self.players[
                player_ids[1]
            ].role = Role.SHERIFF

            self.players[
                player_ids[2]
            ].role = Role.DOCTOR

    async def send_roles(self):
        for player in list(
            self.players.values()
        ):
            if player.role is None:
                continue

            try:
                await self.send_private(
                    player.user_id,
                    self.role_card(player),
                    self,
                    None,
                )
            except Exception:
                logger.exception(
                    "Не удалось отправить роль %s",
                    player.user_id,
                )

    async def game_loop(self):
        try:
            while (
                not self.closed
                and self.phase
                != Phase.FINISHED
            ):
                if self.phase == Phase.NIGHT:
                    await self.night_phase()

                if (
                    self.phase
                    == Phase.FINISHED
                ):
                    break

                if await self.check_win_condition():
                    break

                if self.phase == Phase.DAY:
                    await self.day_phase()

                if (
                    self.phase
                    == Phase.FINISHED
                ):
                    break

                if await self.check_win_condition():
                    break

                if self.phase == Phase.VOTING:
                    await self.voting_phase()

                if (
                    self.phase
                    == Phase.FINISHED
                ):
                    break

                if await self.check_win_condition():
                    break

                self.round_number += 1
                self.phase = Phase.NIGHT

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception(
                "Ошибка игрового цикла Маньяка"
            )

    async def night_phase(self):
        if self.closed:
            return

        self.phase = Phase.NIGHT

        for player in self.players.values():
            player.night_target = None
            player.sheriff_target = None
            player.doctor_target = None

        await self.update_lobby_message()

        await self.send_message(
            self.peer_id,
            self.night_public_text(),
            None,
        )

        await self.send_private_actions()

        for _ in range(
            self.NIGHT_TIME
        ):
            if self.closed:
                return

            if self.night_actions_complete():
                break

            await asyncio.sleep(1)

        await self.resolve_night()

        if self.phase != Phase.FINISHED:
            self.phase = Phase.DAY

    async def send_private_actions(self):
        maniac = self.maniac
        sheriff = self.sheriff
        doctor = self.doctor

        if maniac and maniac.alive:
            await self.send_private(
                maniac.user_id,
                (
                    "🔪 НОЧЬ\n\n"
                    "Вы — МАНЬЯК.\n\n"
                    "Выберите жертву:\n"
                    "!убить ID\n\n"
                    f"⏱ Время: {self.NIGHT_TIME} секунд."
                ),
                self,
                None,
            )

        if sheriff and sheriff.alive:
            await self.send_private(
                sheriff.user_id,
                (
                    "🕵️ НОЧЬ\n\n"
                    "Вы — ШЕРИФ.\n\n"
                    "Проверьте игрока:\n"
                    "!проверить ID\n\n"
                    f"⏱ Время: {self.NIGHT_TIME} секунд."
                ),
                self,
                None,
            )

        if doctor and doctor.alive:
            await self.send_private(
                doctor.user_id,
                (
                    "🩺 НОЧЬ\n\n"
                    "Вы — ДОКТОР.\n\n"
                    "Выберите игрока для защиты:\n"
                    "!защитить ID\n\n"
                    f"⏱ Время: {self.NIGHT_TIME} секунд."
                ),
                self,
                None,
            )

    def night_actions_complete(self) -> bool:
        maniac = self.maniac
        sheriff = self.sheriff
        doctor = self.doctor

        maniac_done = (
            maniac is None
            or not maniac.alive
            or maniac.night_target is not None
        )

        sheriff_done = (
            sheriff is None
            or not sheriff.alive
            or sheriff.sheriff_target is not None
        )

        doctor_done = (
            doctor is None
            or not doctor.alive
            or doctor.doctor_target is not None
        )

        return (
            maniac_done
            and sheriff_done
            and doctor_done
        )

    async def resolve_night(self):
        maniac = self.maniac
        doctor = self.doctor
        sheriff = self.sheriff

        victim_id = (
            maniac.night_target
            if maniac and maniac.alive
            else None
        )

        protected_id = (
            doctor.doctor_target
            if doctor and doctor.alive
            else None
        )

        victim = (
            self.players.get(victim_id)
            if victim_id is not None
            else None
        )

        if victim and victim.alive:
            if victim.user_id == protected_id:
                await self.send_message(
                    self.peer_id,
                    (
                        "🌅 НАСТУПИЛО УТРО\n\n"
                        "🩺 Ночью было нападение,\n"
                        "но доктор спас игрока.\n\n"
                        "❤️ Никто не выбыл."
                    ),
                    None,
                )
            else:
                victim.alive = False

                await self.send_message(
                    self.peer_id,
                    (
                        "🌅 НАСТУПИЛО УТРО\n\n"
                        f"💀 Ночью выбыл "
                        f"{self.mention(victim)}.\n\n"
                        f"🎭 Роль: "
                        f"{self.role_name(victim.role)}\n\n"
                        f"❤️ Живых: {self.alive_count}"
                    ),
                    None,
                )
        else:
            await self.send_message(
                self.peer_id,
                (
                    "🌅 НАСТУПИЛО УТРО\n\n"
                    "🌙 Ночь прошла спокойно.\n"
                    "💚 Никто не выбыл."
                ),
                None,
            )

        if sheriff and sheriff.alive:
            target = (
                self.players.get(
                    sheriff.sheriff_target
                )
                if sheriff.sheriff_target is not None
                else None
            )

            if target:
                result = (
                    "🔴 Да, это Маньяк."
                    if target.role == Role.MANIAC
                    else "🟢 Нет, это не Маньяк."
                )

                await self.send_private(
                    sheriff.user_id,
                    (
                        "🕵️ РЕЗУЛЬТАТ ПРОВЕРКИ\n\n"
                        f"Игрок: {self.mention(target)}\n\n"
                        f"{result}"
                    ),
                    self,
                    None,
                )

    async def day_phase(self):
        if self.closed:
            return

        self.phase = Phase.DAY

        await self.update_lobby_message()

        await self.send_message(
            self.peer_id,
            self.day_text(),
            None,
        )

        await asyncio.sleep(
            self.DAY_TIME
        )

        if not self.closed:
            self.phase = Phase.VOTING

    async def voting_phase(self):
        if self.closed:
            return

        self.phase = Phase.VOTING

        for player in self.players.values():
            player.vote_target = None
            player.votes_received = 0

        await self.update_lobby_message()

        await self.send_message(
            self.peer_id,
            self.voting_text(),
            None,
        )

        await self.send_private_voting()

        for _ in range(
            self.VOTING_TIME
        ):
            if self.closed:
                return

            if self.all_votes_cast():
                break

            await asyncio.sleep(1)

        await self.resolve_voting()

    async def send_private_voting(self):
        for player in self.alive_players():
            await self.send_private(
                player.user_id,
                (
                    "🗳 ГОЛОСОВАНИЕ\n\n"
                    "Выберите игрока:\n"
                    "!голос ID\n\n"
                    "Или:\n"
                    "!пропуск\n\n"
                    f"⏱ Время: {self.VOTING_TIME} секунд."
                ),
                self,
                None,
            )

    def all_votes_cast(self) -> bool:
        alive = self.alive_players()

        if not alive:
            return True

        return all(
            player.vote_target is not None
            for player in alive
        )

    async def resolve_voting(self):
        alive = self.alive_players()

        for voter in alive:
            target_id = voter.vote_target

            if target_id is None:
                continue

            target = self.players.get(
                target_id
            )

            if target and target.alive:
                target.votes_received += 1

        candidates = [
            player
            for player in alive
            if player.votes_received > 0
        ]

        if not candidates:
            await self.send_message(
                self.peer_id,
                (
                    "🗳 РЕЗУЛЬТАТ ГОЛОСОВАНИЯ\n\n"
                    "Никто не получил голосов.\n\n"
                    "💚 Никто не выбыл."
                ),
                None,
            )
            return

        highest = max(
            player.votes_received
            for player in candidates
        )

        winners = [
            player
            for player in candidates
            if player.votes_received == highest
        ]

        if len(winners) != 1:
            lines = [
                (
                    f"• {self.mention(player)} — "
                    f"{player.votes_received}"
                )
                for player in winners
            ]

            await self.send_message(
                self.peer_id,
                (
                    "🗳 РЕЗУЛЬТАТ ГОЛОСОВАНИЯ\n\n"
                    "⚖️ Ничья.\n\n"
                    + "\n".join(lines)
                    + "\n\n💚 Никто не выбыл."
                ),
                None,
            )

            return

        eliminated = winners[0]

        eliminated.alive = False

        await self.send_message(
            self.peer_id,
            (
                "🗳 РЕЗУЛЬТАТ ГОЛОСОВАНИЯ\n\n"
                f"💀 Выбывает "
                f"{self.mention(eliminated)}.\n\n"
                f"🎭 Роль: "
                f"{self.role_name(eliminated.role)}\n\n"
                f"❤️ Живых: {self.alive_count}"
            ),
            None,
        )

    async def maniac_target(
        self,
        user_id: int,
        target_id: int,
    ) -> tuple[bool, str]:

        if self.phase != Phase.NIGHT:
            return (
                False,
                "❌ Сейчас не ночь.",
            )

        player = self.players.get(
            int(user_id)
        )

        if not player:
            return (
                False,
                "❌ Вы не участвуете в игре.",
            )

        if player.role != Role.MANIAC:
            return (
                False,
                "❌ Эта команда доступна только Маньяку.",
            )

        if not player.alive:
            return (
                False,
                "❌ Вы выбыли.",
            )

        target = self.players.get(
            int(target_id)
        )

        if not target or not target.alive:
            return (
                False,
                "❌ Игрок не найден или уже выбыл.",
            )

        if target.user_id == player.user_id:
            return (
                False,
                "❌ Нельзя выбрать себя.",
            )

        player.night_target = (
            target.user_id
        )

        return (
            True,
            f"🔪 Цель выбрана: {self.mention(target)}",
        )

    async def sheriff_check(
        self,
        user_id: int,
        target_id: int,
    ) -> tuple[bool, str]:

        if self.phase != Phase.NIGHT:
            return (
                False,
                "❌ Сейчас не ночь.",
            )

        player = self.players.get(
            int(user_id)
        )

        if not player:
            return (
                False,
                "❌ Вы не участвуете в игре.",
            )

        if player.role != Role.SHERIFF:
            return (
                False,
                "❌ Команда доступна только Шерифу.",
            )

        if not player.alive:
            return (
                False,
                "❌ Вы выбыли.",
            )

        target = self.players.get(
            int(target_id)
        )

        if not target or not target.alive:
            return (
                False,
                "❌ Игрок не найден или уже выбыл.",
            )

        if target.user_id == player.user_id:
            return (
                False,
                "❌ Нельзя проверить себя.",
            )

        player.sheriff_target = (
            target.user_id
        )

        return (
            True,
            f"🕵️ Проверка выбрана: {self.mention(target)}",
        )

    async def doctor_protect(
        self,
        user_id: int,
        target_id: int,
    ) -> tuple[bool, str]:

        if self.phase != Phase.NIGHT:
            return (
                False,
                "❌ Сейчас не ночь.",
            )

        player = self.players.get(
            int(user_id)
        )

        if not player:
            return (
                False,
                "❌ Вы не участвуете в игре.",
            )

        if player.role != Role.DOCTOR:
            return (
                False,
                "❌ Команда доступна только Доктору.",
            )

        if not player.alive:
            return (
                False,
                "❌ Вы выбыли.",
            )

        target = self.players.get(
            int(target_id)
        )

        if not target or not target.alive:
            return (
                False,
                "❌ Игрок не найден или уже выбыл.",
            )

        player.doctor_target = (
            target.user_id
        )

        return (
            True,
            f"🩺 Защита выбрана: {self.mention(target)}",
        )

    async def vote(
        self,
        user_id: int,
        target_id: int,
    ) -> tuple[bool, str]:

        if self.phase != Phase.VOTING:
            return (
                False,
                "❌ Сейчас голосование не идёт.",
            )

        player = self.players.get(
            int(user_id)
        )

        if not player:
            return (
                False,
                "❌ Вы не участвуете в игре.",
            )

        if not player.alive:
            return (
                False,
                "❌ Вы выбыли.",
            )

        target = self.players.get(
            int(target_id)
        )

        if not target or not target.alive:
            return (
                False,
                "❌ Игрок не найден или уже выбыл.",
            )

        if target.user_id == player.user_id:
            return (
                False,
                "❌ Нельзя голосовать за себя.",
            )

        player.vote_target = target.user_id

        return (
            True,
            f"🗳 Вы проголосовали за {self.mention(target)}.",
        )

    async def vote_skip(
        self,
        user_id: int,
    ) -> tuple[bool, str]:

        if self.phase != Phase.VOTING:
            return (
                False,
                "❌ Сейчас голосование не идёт.",
            )

        player = self.players.get(
            int(user_id)
        )

        if not player:
            return (
                False,
                "❌ Вы не участвуете в игре.",
            )

        if not player.alive:
            return (
                False,
                "❌ Вы выбыли.",
            )

        # Специальное значение 0 означает пропуск.
        player.vote_target = 0

        return (
            True,
            "⏭ Вы пропустили голосование.",
        )

    async def check_win_condition(self) -> bool:
        if self._finish_started:
            return True

        maniac = self.maniac

        if (
            maniac is None
            or not maniac.alive
        ):
            self._finish_started = True

            await self.finish_game(
                winner="civilians",
                winner_text="🏆 ПОБЕДА МИРНЫХ!",
            )

            return True

        alive_maniacs = sum(
            1
            for player in self.alive_players()
            if player.role == Role.MANIAC
        )

        alive_innocents = sum(
            1
            for player in self.alive_players()
            if player.role != Role.MANIAC
        )

        if (
            alive_maniacs
            >= alive_innocents
        ):
            self._finish_started = True

            await self.finish_game(
                winner="maniac",
                winner_text="🔪 ПОБЕДА МАНЬЯКА!",
            )

            return True

        return False

    async def finish_game(
        self,
        winner: str,
        winner_text: str,
    ):
        if self.phase == Phase.FINISHED:
            return

        self.phase = Phase.FINISHED

        self.result = GameResult(
            winner=winner,
            winner_text=winner_text,
        )

        await self.update_lobby_message()

        players = list(
            self.players.values()
        )

        role_lines = []

        for player in players:
            status = (
                "💚"
                if player.alive
                else "💀"
            )

            role_lines.append(
                (
                    f"{status} "
                    f"{self.mention(player)} "
                    f"— {self.role_name(player.role)}"
                )
            )

        text = (
            f"{winner_text}\n\n"
            "📋 РЕЗУЛЬТАТЫ\n\n"
            + "\n".join(role_lines)
        )

        mvp = self.calculate_mvp()

        if mvp:
            text += (
                "\n\n"
                f"⭐ MVP: {self.mention(mvp)}"
            )

        text += (
            "\n\n"
            f"🎲 Раундов: {self.round_number}"
        )

        result_message_id = (
            await self.send_message(
                self.peer_id,
                text,
                None,
            )
        )

        await self.save_statistics(
            winner
        )

        if result_message_id:
            await asyncio.sleep(
                self.RESULT_DELETE_DELAY
            )

            try:
                await self.delete_message(
                    self.peer_id,
                    result_message_id,
                )
            except Exception:
                logger.exception(
                    "Не удалось удалить результаты"
                )

        self.closed = True

    async def save_statistics(
        self,
        winner: str,
    ):
        for player in self.players.values():
            if winner == "maniac":
                won = (
                    player.role
                    == Role.MANIAC
                )
            else:
                won = (
                    player.role
                    != Role.MANIAC
                )

            try:
                await self.save_stats(
                    player,
                    won,
                )
            except Exception:
                logger.exception(
                    "Ошибка статистики %s",
                    player.user_id,
                )

    def calculate_mvp(
        self,
    ) -> Player | None:

        alive = [
            player
            for player in self.players.values()
            if player.alive
        ]

        if not alive:
            return None

        priority = {
            Role.MANIAC: 4,
            Role.SHERIFF: 3,
            Role.DOCTOR: 2,
            Role.CIVILIAN: 1,
        }

        alive.sort(
            key=lambda player: (
                priority.get(
                    player.role,
                    0,
                ),
                player.user_id,
            ),
            reverse=True,
        )

        return alive[0]

    async def close(
        self,
        delete_lobby: bool = True,
    ):
        self.closed = True
        self.phase = Phase.FINISHED

        current_task = (
            asyncio.current_task()
        )

        if (
            self.task
            and self.task is not current_task
            and not self.task.done()
        ):
            self.task.cancel()

            try:
                await self.task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception(
                    "Ошибка закрытия игры"
                )

        if self.lobby_message_id:
            try:
                await self.unpin_message(
                    self.peer_id,
                    self.lobby_message_id,
                )
            except Exception:
                pass

            if delete_lobby:
                try:
                    await self.delete_message(
                        self.peer_id,
                        self.lobby_message_id,
                    )
                except Exception:
                    pass

            self.lobby_message_id = None

    async def create_lobby_message(self):
        if self.closed:
            return

        message_id = (
            await self.send_message(
                self.peer_id,
                self.lobby_text(),
                None,
            )
        )

        self.lobby_message_id = (
            message_id
        )

        if message_id:
            try:
                await self.pin_message(
                    self.peer_id,
                    message_id,
                )
            except Exception:
                logger.warning(
                    "Не удалось закрепить лобби"
                )

    async def update_lobby_message(self):
        if not self.lobby_message_id:
            return

        try:
            text = (
                self.lobby_text()
                if self.phase == Phase.LOBBY
                else self.status_text()
            )

            await self.edit_message(
                self.peer_id,
                self.lobby_message_id,
                text,
                None,
            )

        except Exception:
            logger.exception(
                "Не удалось обновить лобби"
            )

    def lobby_text(self) -> str:
        players = list(
            self.players.values()
        )

        lines = [
            "🎲 МАНЬЯК",
            "",
            (
                "👑 Создатель: "
                f"{self.mention(self.players.get(self.creator_id))}"
            ),
            "",
            (
                f"👥 Игроки: "
                f"{len(players)}/{self.MAX_PLAYERS}"
            ),
            "",
        ]

        for index, player in enumerate(
            players,
            start=1,
        ):
            lines.append(
                f"{index}. {self.mention(player)}"
            )

        lines.extend(
            [
                "",
                "⏳ Ожидание игроков...",
                "",
                f"Минимум: {self.MIN_PLAYERS}",
                "",
                "Команды:",
                "!войти — войти",
                "!выйти — выйти",
                "!старт — начать",
                "!стоп — закрыть",
            ]
        )

        return "\n".join(lines)

    def status_text(self) -> str:
        return (
            "🎲 МАНЬЯК\n\n"
            f"{self.phase_text()}\n\n"
            f"🎯 Раунд: {self.round_number}\n"
            f"👥 Игроков: {self.player_count}/{self.MAX_PLAYERS}\n"
            f"❤️ Живых: {self.alive_count}\n"
            f"💀 Выбыли: {self.dead_count}"
        )

    def night_public_text(self) -> str:
        return (
            "🌙 НОЧЬ\n\n"
            f"🎯 Раунд: {self.round_number}\n"
            f"👥 Игроков: {self.player_count}/{self.MAX_PLAYERS}\n"
            f"❤️ Живых: {self.alive_count}\n"
            f"💀 Выбыли: {self.dead_count}\n\n"
            "🔪 Маньяк выбирает жертву\n"
            "🕵️ Шериф проводит проверку\n"
            "🩺 Доктор выбирает защиту\n\n"
            "📩 Действия выполняются в ЛС боту.\n\n"
            f"⏱ Ночь: {self.NIGHT_TIME} секунд."
        )

    def day_text(self) -> str:
        return (
            "☀️ ДЕНЬ\n\n"
            f"🎯 Раунд: {self.round_number}\n"
            f"❤️ Живых: {self.alive_count}\n"
            f"💀 Выбыли: {self.dead_count}\n\n"
            "💬 Обсудите происходящее.\n"
            "Кто может быть Маньяком?\n\n"
            f"⏱ Обсуждение: {self.DAY_TIME} секунд."
        )

    def voting_text(self) -> str:
        return (
            "🗳 ГОЛОСОВАНИЕ\n\n"
            f"❤️ Живых: {self.alive_count}\n\n"
            "Выберите подозреваемого.\n\n"
            "!голос ID\n"
            "!пропуск\n\n"
            f"⏱ Время: {self.VOTING_TIME} секунд."
        )

    def role_card(
        self,
        player: Player,
    ) -> str:

        if player.role == Role.MANIAC:
            return (
                "🔪 ВАША РОЛЬ\n\n"
                "Вы — МАНЬЯК.\n\n"
                "Ваша задача — остаться в живых.\n\n"
                "Ночью:\n"
                "!убить ID\n\n"
                "⚠️ Не раскрывайте свою роль."
            )

        if player.role == Role.SHERIFF:
            return (
                "🕵️ ВАША РОЛЬ\n\n"
                "Вы — ШЕРИФ.\n\n"
                "Ваша задача — найти Маньяка.\n\n"
                "Ночью:\n"
                "!проверить ID"
            )

        if player.role == Role.DOCTOR:
            return (
                "🩺 ВАША РОЛЬ\n\n"
                "Вы — ДОКТОР.\n\n"
                "Ваша задача — спасать игроков.\n\n"
                "Ночью:\n"
                "!защитить ID"
            )

        return (
            "👤 ВАША РОЛЬ\n\n"
            "Вы — МИРНЫЙ ЖИТЕЛЬ.\n\n"
            "Ваша задача — вычислить Маньяка.\n\n"
            "Участвуйте в обсуждении и голосовании."
        )

    def alive_players(self) -> list[Player]:
        return [
            player
            for player in self.players.values()
            if player.alive
        ]

    def find_role(
        self,
        role: Role,
    ) -> Player | None:

        for player in self.players.values():
            if player.role == role:
                return player

        return None

    def mention(
        self,
        player: Player | None,
    ) -> str:

        if player is None:
            return "[id0|Игрок]"

        name = (
            player.first_name
            or "Игрок"
        )

        name = (
            str(name)
            .replace("[", "")
            .replace("]", "")
            .strip()
        )

        return (
            f"[id{player.user_id}|{ name}]"
        )

    def role_name(
        self,
        role: Role | None,
    ) -> str:

        mapping = {
            Role.MANIAC: "🔪 Маньяк",
            Role.SHERIFF: "🕵️ Шериф",
            Role.DOCTOR: "🩺 Доктор",
            Role.CIVILIAN: "👤 Мирный",
        }

        return mapping.get(
            role,
            "❔ Неизвестно",
        )

    def phase_text(self) -> str:
        mapping = {
            Phase.LOBBY: "⏳ ЛОББИ",
            Phase.NIGHT: "🌙 НОЧЬ",
            Phase.DAY: "☀️ ДЕНЬ",
            Phase.VOTING: "🗳 ГОЛОСОВАНИЕ",
            Phase.FINISHED: "🏁 ИГРА ОКОНЧЕНА",
        }

        return mapping.get(
            self.phase,
            "🎲 ИГРА",
        )