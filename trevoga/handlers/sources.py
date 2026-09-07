import logging

from telethon import events

from trevoga.handlers.context import HandlerContext
from trevoga.services.text_cleaner import (
    clean_text,
    detect_keywords,
    format_post_html,
    matching_photos,
    watermark,
)


logger = logging.getLogger(__name__)


def register(client, context: HandlerContext):
    @client.on(events.NewMessage(chats=context.settings.source_channels))
    async def forward_to_group_c(event):
        # Album items also emit NewMessage events; the Album handler publishes them together.
        if event.message.grouped_id:
            return
        await _forward_messages([event.message], event.chat_id, client, context)

    @client.on(events.Album(chats=context.settings.source_channels))
    async def forward_album_to_group_c(event):
        await _forward_messages(event.messages, event.chat_id, client, context)


async def _notify_subscribers(text, caption, messages, client, context: HandlerContext):
    if not context.subscriptions:
        return
    lowered = text.lower()
    notified = set()
    for keyword in context.subscriptions.all_keywords():
        if keyword in lowered:
            for user_id in context.subscriptions.find_by_keyword(keyword):
                if user_id in notified:
                    continue
                notified.add(user_id)
                try:
                    media = [item.media for item in messages if item.media]
                    if not media:
                        media = matching_photos(text, context.rules)
                    if media:
                        await client.send_file(
                            user_id,
                            media,
                            caption=caption,
                            parse_mode="html",
                            link_preview=False,
                        )
                    else:
                        await client.send_message(
                            user_id, caption, parse_mode="html", link_preview=False
                        )
                except Exception:
                    logger.exception("Failed to notify subscriber %s", user_id)


async def _forward_messages(messages, chat_id, client, context: HandlerContext):
    message = messages[0]
    text = clean_text(next((item.raw_text for item in messages if item.raw_text), ""))
    body = format_post_html(text, context.rules)
    photos = matching_photos(text, context.rules)
    caption = (
        f"{body}\n\n{watermark()}"
        if body
        else watermark()
        if photos or any(item.media for item in messages)
        else ""
    )
    context.statistics.repository.record(
        "to_c",
        source=str(chat_id),
        keywords=detect_keywords(text, context.rules),
    )
    await _notify_subscribers(text, caption, messages, client, context)
    try:
        if photos:
            sent = await client.send_file(
                context.settings.group_c,
                photos,
                caption=caption,
                parse_mode="html",
                link_preview=False,
            )
        elif any(item.media for item in messages):
            sent = await client.send_file(
                context.settings.group_c,
                [item.media for item in messages if item.media],
                caption=caption,
                parse_mode="html",
                link_preview=False,
            )
        else:
            sent = await client.send_message(
                context.settings.group_c, caption, parse_mode="html", link_preview=False
            )
        sent_message = sent[0] if isinstance(sent, list) else sent
        context.moderation.schedule_check(sent_message.id, text, caption)
    except Exception:
        logger.exception("Failed to publish source message %s", message.id)
