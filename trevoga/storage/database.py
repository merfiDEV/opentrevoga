import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS forwarded_messages (
                    source_message_id INTEGER NOT NULL,
                    target TEXT NOT NULL,
                    target_message_id INTEGER NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'main',
                    PRIMARY KEY (source_message_id, target, target_message_id)
                );
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    source TEXT,
                    keywords TEXT NOT NULL DEFAULT '[]',
                    message_id INTEGER,
                    created_at REAL NOT NULL
                );
                """
            )
