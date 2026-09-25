"""Доступ к таблице подписок в общей trevoga.db."""

import sqlite3
import time
from pathlib import Path


class SubscriptionStore:
    """Чтение/запись подписок в таблице subscriptions (общая БД с юзерботом)."""

    def __init__(self, database_path: Path):
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def add(self, user_id: int, keyword: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO subscriptions VALUES (?, ?, ?)",
                (user_id, keyword, time.time()),
            )

    def remove(self, user_id: int, keyword: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM subscriptions WHERE user_id = ? AND keyword = ?",
                (user_id, keyword),
            )
        return cursor.rowcount > 0

    def remove_all(self, user_id: int) -> int:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))
        return cursor.rowcount

    def list_for_user(self, user_id: int) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT keyword FROM subscriptions WHERE user_id = ? ORDER BY keyword",
                (user_id,),
            ).fetchall()
        return [row["keyword"] for row in rows]

    def all_keywords(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT keyword FROM subscriptions ORDER BY keyword"
            ).fetchall()
        return [row["keyword"] for row in rows]

    def find_by_keyword(self, keyword: str) -> list[int]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT user_id FROM subscriptions WHERE keyword = ?", (keyword,)
            ).fetchall()
        return [row["user_id"] for row in rows]

    def user_count(self) -> int:
        """Количество уникальных подписчиков."""
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(DISTINCT user_id) FROM subscriptions").fetchone()
        return row[0] if row else 0

    def keyword_stats(self) -> list[tuple[str, int]]:
        """Список (ключевое слово, число подписчиков) по убыванию."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT keyword, COUNT(*) AS n FROM subscriptions "
                "GROUP BY keyword ORDER BY n DESC, keyword"
            ).fetchall()
        return [(row["keyword"], row["n"]) for row in rows]

    def total_subscriptions(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM subscriptions").fetchone()
        return row[0] if row else 0
