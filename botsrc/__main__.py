"""Запуск бота-подписчика: python -m botsrc."""

import asyncio
import logging

from botsrc.bot import run_bot
from botsrc.config import load_bot_settings


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def _main() -> None:
    _setup_logging()
    settings = load_bot_settings()
    if not settings.token:
        raise SystemExit("BOT_TOKEN is not set in .env")
    if not settings.group_c:
        raise SystemExit("GROUP_C is not set in .env")
    await run_bot(settings)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Interrupted by user")
