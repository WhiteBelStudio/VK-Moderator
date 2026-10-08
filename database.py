import os
import sqlite3
from typing import Any


class ManiacDatabase:
    def __init__(self):
        base_dir = os.path.dirname(__file__)
        data_dir = os.path.join(
            base_dir,
            "data",
        )

        os.makedirs(
            data_dir,
            exist_ok=True,
        )

        self.path = os.path.join(
            data_dir,
            "maniac.db",
        )

        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=30,
        )

        connection.row_factory = sqlite3.Row

        return connection

    def _init_db(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS players (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT NOT NULL DEFAULT '',
                    games INTEGER NOT NULL DEFAULT 0,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    maniac_games INTEGER NOT NULL DEFAULT 0,
                    sheriff_games INTEGER NOT NULL DEFAULT 0,
                    doctor_games INTEGER NOT NULL DEFAULT 0,
                    civilian_games INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            connection.commit()

    def ensure_player(
        self,
        user_id: int,
        first_name: str,
    ):
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO players (
                    user_id,
                    first_name
                )
                VALUES (?, ?)
                ON CONFLICT(user_id)
                DO UPDATE SET
                    first_name = excluded.first_name
                """,
                (
                    user_id,
                    first_name,
                ),
            )

            connection.commit()

    def record_game(
        self,
        user_id: int,
        first_name: str,
        role: str,
        won: bool,
    ):
        self.ensure_player(
            user_id=user_id,
            first_name=first_name,
        )

        role_column = {
            "maniac": "maniac_games",
            "sheriff": "sheriff_games",
            "doctor": "doctor_games",
            "civilian": "civilian_games",
        }.get(role)

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE players
                SET
                    games = games + 1,
                    wins = wins + ?,
                    losses = losses + ?
                WHERE user_id = ?
                """,
                (
                    1 if won else 0,
                    0 if won else 1,
                    user_id,
                ),
            )

            if role_column:
                connection.execute(
                    f"""
                    UPDATE players
                    SET {role_column} = {role_column} + 1
                    WHERE user_id = ?
                    """,
                    (user_id,),
                )

            connection.commit()

    def get_stats(
        self,
        user_id: int,
    ) -> sqlite3.Row | None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT *
                FROM players
                WHERE user_id = ?
                """,
                (user_id,),
            )

            return cursor.fetchone()

    def get_top(
        self,
        limit: int = 10,
    ) -> list[sqlite3.Row]:
        limit = max(
            1,
            min(limit, 50),
        )

        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT *
                FROM players
                WHERE games > 0
                ORDER BY
                    wins DESC,
                    games DESC
                LIMIT ?
                """,
                (limit,),
            )

            return cursor.fetchall()