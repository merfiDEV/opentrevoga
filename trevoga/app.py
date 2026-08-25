import asyncio
import logging

from telethon import utils

from trevoga.config import load_settings
from trevoga.handlers.comments import register as register_comments
from trevoga.handlers.commands import register as register_commands
from trevoga.handlers.context import HandlerContext
from trevoga.handlers.reactions import register as register_reactions
from trevoga.handlers.sources import register as register_sources
from trevoga.integrations.ai_client import AIClient
from trevoga.integrations.telegram import create_client
from trevoga.services.moderation import ModerationService
from trevoga.services.publishing import PublishingService
from trevoga.services.statistics import StatisticsService
from trevoga.services.text_cleaner import photo_rules, set_watermark
from trevoga.storage.database import Database
from trevoga.storage.repositories import (
    ForwardedPostRepository,
    ModerationRepository,
    StatisticsRepository,
)


async def run():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = load_settings()
    set_watermark(settings.watermark_enabled)
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
    publisher = PublishingService(client, settings, posts, stats_repository)
    await client.start()
    await publisher.validate_channel_targets()
    entity = await client.get_entity(settings.group_c)
    context = HandlerContext(
        client,
        settings,
        photo_rules(settings.assets_dir),
        publisher,
        moderation,
        statistics,
        utils.get_peer_id(entity),
        moderation_repository,
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
    register_comments(client, context)
    register_reactions(client, context)
    register_commands(client, context)
    asyncio.create_task(_cleanup_loop(stats_repository))
    await client.run_until_disconnected()


async def _cleanup_loop(repository):
    while True:
        await asyncio.sleep(1800)
        repository.cleanup()
