import json
import time
from collections import Counter

from trevoga.models import ForwardedPost
from trevoga.storage.database import Database


class ForwardedPostRepository:
    def __init__(self, database: Database):
        self.database = database

    def exists(self, source_message_id: int) -> bool:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM forwarded_messages WHERE source_message_id = ? LIMIT 1",
                (source_message_id,),
            ).fetchone()
        return row is not None

    def get(self, source_message_id: int) -> ForwardedPost | None:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT target, target_message_id, kind FROM forwarded_messages WHERE source_message_id = ?",
                (source_message_id,),
            ).fetchall()
        if not rows:
            return None
        post = ForwardedPost(source_message_id)
        for row in rows:
            if row["kind"] == "main":
                post.main[row["target"]] = row["target_message_id"]
            else:
                post.comments.append((row["target"], row["target_message_id"]))
        return post

    def save_main(self, source_message_id: int, messages: dict[str, int]) -> None:
        with self.database.connect() as connection:
            connection.executemany(
                "INSERT OR IGNORE INTO forwarded_messages VALUES (?, ?, ?, 'main')",
                [
                    (source_message_id, target, message_id)
                    for target, message_id in messages.items()
                ],
            )

    def delete(self, source_message_id: int) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "DELETE FROM forwarded_messages WHERE source_message_id = ?",
                (source_message_id,),
            )


class StatisticsRepository:
    def __init__(self, database: Database):
        self.database = database

    def record(
        self, kind: str, source: str | None = None, keywords=None, message_id=None
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO statistics(kind, source, keywords, message_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    kind,
                    source,
                    json.dumps(keywords or [], ensure_ascii=False),
                    message_id,
                    time.time(),
                ),
            )

    def keyword_counts(self, hours: int) -> Counter:
        cutoff = time.time() - hours * 3600
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT keywords FROM statistics WHERE kind = 'to_c' AND created_at >= ?",
                (cutoff,),
            ).fetchall()
        return Counter(word for row in rows for word in json.loads(row["keywords"]))

    def cleanup(self, ttl_hours: int = 24) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "DELETE FROM statistics WHERE created_at < ?",
                (time.time() - ttl_hours * 3600,),
            )
