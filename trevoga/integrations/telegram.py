from telethon import TelegramClient

from trevoga.config import Settings


def create_client(settings: Settings) -> TelegramClient:
    return TelegramClient(
        str(settings.session_path),
        settings.api_id,
        settings.api_hash,
        catch_up=True,
    )
