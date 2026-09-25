import asyncio
import contextlib
import logging
from logging.handlers import RotatingFileHandler

from telethon import utils

from trevoga import health
from trevoga.config import load_settings
from trevoga.handlers.comments import register as register_comments
from trevoga.handlers.channel_moderation import register as register_channel_moderation
from trevoga.handlers.commands import register as register_commands
from trevoga.handlers.context import HandlerContext
from trevoga.handlers.reactions import register as register_reactions
from trevoga.handlers.sources import register as register_sources
from trevoga.integrations.ai_client import AIClient
from trevoga.integrations.telegram import create_client
from trevoga.services.fix_service import FixService
from trevoga.services.moderation import ModerationService
from trevoga.services.publishing import PublishingService
from trevoga.services.statistics import StatisticsService
from trevoga.services.text_cleaner import photo_rules, set_cards, set_watermark
from trevoga.storage.database import Database
from trevoga.storage.repositories import (
    ForwardedPostRepository,
    ModerationRepository,
    StatisticsRepository,
)


def _setup_logging(log_path) -> None:
    """Log to stdout and a rotating file; remember the last ERROR in memory."""
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(stream)
    try:
        file_handler = RotatingFileHandler(
            log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as error:
        root.warning("File logging disabled: %s", error)
    error_handler = health.LastErrorHandler()
    error_handler.setFormatter(formatter)
    root.addHandler(error_handler)


async def run():
    settings = load_settings()
    _setup_logging(settings.log_path)
    set_watermark(settings.watermark_enabled)
    set_cards(settings.cards_enabled)
    settings.validate()
    database = Database(settings.database_path)
    database.initialize()
    client = create_client(settings)
    posts = ForwardedPostRepository(database)
    stats_repository = StatisticsRepository(database)
    moderation_repository = ModerationRepository(database)
    statistics = StatisticsService(stats_repository)
    moderation = ModerationService(
        AIClient(
            settings.ai_api_base,
            settings.ai_model,
            settings.ai_api_key,
            settings.ai_timeout,
        ),
        AIClient(
            settings.ai_fix_api_base,
            settings.ai_fix_model,
            settings.ai_fix_api_key,
            settings.ai_fix_timeout,
        ),
        settings.ai_mode,
        settings.ai_check_delay,
    )
    if settings.ai_mode:
        available, response = await moderation.enable()
        if not available:
            logging.getLogger(__name__).warning(
                "AI_MODE is enabled in configuration, but AI is unavailable: %s",
                response,
            )
    fixer = FixService(moderation, autocheck_enabled=settings.aicheck_enabled)
    publisher = PublishingService(client, settings, posts, stats_repository)
    await client.start()
    await publisher.validate_channel_targets()
    entity = await client.get_entity(settings.group_c)
    source_channels = await _resolve_source_channels(client, settings)
    context = HandlerContext(
        client,
        settings,
        photo_rules(settings.assets_dir),
        publisher,
        moderation,
        statistics,
        utils.get_peer_id(entity),
        moderation_repository,
        set(settings.ignored_channels),
        source_channels,
        fixer,
    )

    async def publish_ai_approved(message_id, caption):
        if posts.exists(message_id):
            return
        message = await client.get_messages(settings.group_c, ids=message_id)
        if not message:
            return
        await client.edit_message(
            settings.group_c, message_id, caption, parse_mode="html", link_preview=False
        )
        messages = [message]
        if message.grouped_id:
            nearby = await client.get_messages(
                settings.group_c, min_id=max(0, message.id - 10), max_id=message.id + 10
            )
            messages = sorted(
                [item for item in nearby if item.grouped_id == message.grouped_id],
                key=lambda item: item.id,
            )
        await publisher.forward_to_targets(messages)

    moderation.on_approved = publish_ai_approved

    async def save_moderation_result(result):
        moderation_repository.save(result)

    moderation.on_moderation_result = save_moderation_result
    register_sources(client, context)
    register_channel_moderation(client, context)
    register_comments(client, context)
    register_reactions(client, context)
    register_commands(client, context)
    cleanup_task = asyncio.create_task(_cleanup_loop(stats_repository))
    try:
        await client.run_until_disconnected()
    finally:
        cleanup_task.cancel()
        await _drain_tasks(cleanup_task)
        await moderation.drain()
        await moderation.aclose()
        await client.disconnect()


async def _resolve_source_channels(client, settings) -> set[int]:
    """Resolve configured SOURCE_CHANNELS entries to canonical peer ids."""
    resolved: set[int] = set()
    for value in settings.source_channels:
        try:
            target = int(value) if value.lstrip("-").isdigit() else value
            entity = await client.get_entity(target)
            resolved.add(utils.get_peer_id(entity))
        except Exception as error:
            logging.getLogger(__name__).warning(
                "Failed to resolve source channel %s: %s", value, error
            )
    return resolved


async def _cleanup_loop(repository):
    while True:
        await asyncio.sleep(1800)
        try:
            repository.cleanup()
        except Exception:
            logging.getLogger(__name__).exception("Statistics cleanup failed")


async def _drain_tasks(*tasks) -> None:
    for task in tasks:
        if task is None:
            continue
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
