import sqlite3
from pathlib import Path


MIGRATIONS = [
    # 1: initial schema
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
    CREATE TABLE IF NOT EXISTS moderation_results (
        message_id INTEGER PRIMARY KEY,
        useful INTEGER NOT NULL,
        reason TEXT,
        reason_text TEXT NOT NULL DEFAULT '',
        confidence REAL,
        raw_response TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL,
        created_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS subscriptions (
        user_id INTEGER NOT NULL,
        keyword TEXT NOT NULL,
        created_at REAL NOT NULL,
        PRIMARY KEY (user_id, keyword)
    );
    """,
    # 2: news index for inline mode (@bot <keyword> -> last news)
    """
    CREATE TABLE IF NOT EXISTS news_index (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_c_message_id INTEGER,
        text TEXT NOT NULL DEFAULT '',
        html TEXT NOT NULL DEFAULT '',
        keywords TEXT NOT NULL DEFAULT '[]',
        photo_file_id TEXT,
        video_file_id TEXT,
        created_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_news_index_created
        ON news_index (created_at DESC);
    """,
    # 3: lowercased mirror of news text for case-insensitive Cyrillic search.
    # SQLite's built-in lower() is ASCII-only, so it can't fold Cyrillic.
    """
    ALTER TABLE news_index ADD COLUMN text_lower TEXT NOT NULL DEFAULT '';
    ALTER TABLE news_index ADD COLUMN keywords_lower TEXT NOT NULL DEFAULT '';
    UPDATE news_index
        SET text_lower = lower(text),
            keywords_lower = lower(keywords);
    """,
]


class Database:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            for index, migration in enumerate(MIGRATIONS[version:], start=version + 1):
                connection.executescript(migration)
                connection.execute(f"PRAGMA user_version = {index}")
