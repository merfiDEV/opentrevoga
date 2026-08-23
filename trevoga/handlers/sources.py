import logging

from telethon import events

from trevoga.handlers.context import HandlerContext
from trevoga.services.text_cleaner import (
    WATERMARK,
    clean_text,
    detect_keywords,
    format_post_html,
    matching_photos,
)


logger = logging.getLogger(__name__)


def register(client, context: HandlerContext):
    @client.on(events.NewMessage(chats=context.settings.source_channels))
    async def forward_to_group_c(event):
        message = event.message
        text = clean_text(message.raw_text or "")
        body = format_post_html(text, context.rules)
        photos = matching_photos(text, context.rules)
        caption = (
            f"{body}\n\n{WATERMARK}"
            if body
            else WATERMARK
            if photos or message.media
            else ""
        )
        context.statistics.repository.record(
            "to_c",
            source=str(event.chat_id),
            keywords=detect_keywords(text, context.rules),
        )
        try:
            if photos:
                sent = await client.send_file(
                    context.settings.group_c, photos, caption=caption, parse_mode="html"
                )
            elif message.media:
                sent = await client.send_file(
                    context.settings.group_c,
                    message.media,
                    caption=caption,
                    parse_mode="html",
                )
            else:
                sent = await client.send_message(
                    context.settings.group_c, caption, parse_mode="html"
                )
            sent_message = sent[0] if isinstance(sent, list) else sent
            context.moderation.schedule_check(sent_message.id, text, caption)
        except Exception:
            logger.exception("Failed to publish source message %s", message.id)
