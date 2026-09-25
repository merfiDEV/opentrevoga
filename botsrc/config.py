"""Конфигурация бота-подписчика: читает тот же .env, что и юзербот."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class BotSettings:
    token: str
    group_c: int
    database_path: Path
    admin_ids: tuple[int, ...]


def load_bot_settings() -> BotSettings:
    load_dotenv(BASE_DIR / ".env")
    return BotSettings(
        token=os.getenv("BOT_TOKEN", "").strip(),
        group_c=int(os.getenv("GROUP_C", "0")),
        database_path=BASE_DIR / os.getenv("DATABASE_FILE_NAME", "trevoga.db"),
        admin_ids=tuple(
            int(value.strip())
            for value in os.getenv("ADMIN_IDS", "").split(",")
            if value.strip().lstrip("-").isdigit()
        ),
    )
