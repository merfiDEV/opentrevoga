import logging
import tempfile
import time
from pathlib import Path

from telethon import events

from trevoga.handlers.context import HandlerContext
from trevoga.services.text_cleaner import (
    clean_text,
    detect_keywords,
    label_links,
    matching_photos,
    render_post,
    watermark,
)
from trevoga.services.watermark import apply_watermark


logger = logging.getLogger(__name__)

# Окно, у межах якого повторне спрацювання того ж ключового слова не надсилається
# підписникам (перше повідомлення перемагає).
SUBSCRIBE_DEDUP_SECONDS = 60


def register(client, context: HandlerContext):
    # keyword -> monotonic timestamp останнього надісланого сповіщення
    notify_state: dict[str, float] = {}

    @client.on(events.NewMessage())
    async def forward_to_group_c(event):
        if event.chat_id not in context.source_channels:
            return
        # Album items also emit NewMessage events; the Album handler publishes them together.
        if event.message.grouped_id:
            return
        await _forward_messages([event.message], event.chat_id, client, context, notify_state)

    @client.on(events.Album())
    async def forward_album_to_group_c(event):
        if event.chat_id not in context.source_channels:
            return
        await _forward_messages(event.messages, event.chat_id, client, context, notify_state)


async def _notify_subscribers(
    text, caption, messages, client, context: HandlerContext, notify_state: dict[str, float]
):
    if not context.subscriptions:
        return
    lowered = text.lower()
    notified = set()
    now = time.monotonic()
    for keyword in context.subscriptions.all_keywords():
        if keyword in lowered:
            last_sent = notify_state.get(keyword)
            if last_sent is not None and now - last_sent < SUBSCRIBE_DEDUP_SECONDS:
                # Про це саме ключове слово вже сповіщали в межах вікна — пропускаємо.
                continue
            notify_state[keyword] = now
            for user_id in context.subscriptions.find_by_keyword(keyword):
                if user_id in notified:
                    continue
                notified.add(user_id)
                try:
                    media = [item.media for item in messages if item.media]
                    fallback = matching_photos(text, context.rules) if not media else []
                    if fallback:
                        with tempfile.TemporaryDirectory(prefix="trevoga-sub-") as directory:
                            watermarked_media = []
                            for photo in fallback:
                                output = Path(directory) / f"watermarked-{photo.name}"
                                await apply_watermark(photo, output)
                                watermarked_media.append(output)
                            await client.send_file(
                                user_id,
                                watermarked_media,
                                caption=caption,
                                parse_mode="html",
                                link_preview=False,
                            )
                    elif media:
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


async def _autocheck_message(client, context: HandlerContext, message_id: int, text: str):
    if not context.fixer or not context.fixer.autocheck_enabled:
        return
    # text — уже очищенное тело поста (без вики-ссылок и вотермарки).
    # После редактуры пересобираем caption целиком: body + label_links + watermark,
    # иначе блок вики-ссылок потеряется.
    source = clean_text(text)
    fixed = await context.fixer.autocheck(source)
    if not fixed or fixed.strip() == source.strip():
        return
    edited = render_post(fixed, context.rules, "\n".join(label_links(fixed, context.rules)))
    try:
        await client.edit_message(
            context.settings.group_c,
            message_id,
            edited,
            parse_mode="html",
            link_preview=False,
        )
    except Exception:
        logger.exception("AI autocheck edit failed for %s", message_id)


async def _forward_messages(messages, chat_id, client, context: HandlerContext, notify_state):
    message = messages[0]
    text = clean_text(next((item.raw_text for item in messages if item.raw_text), ""))
    photos = matching_photos(text, context.rules)
    links_html = "\n".join(label_links(text, context.rules))
    has_media = bool(photos) or any(item.media for item in messages)
    caption = render_post(text, context.rules, links_html) if (text or links_html) else ""
    # Без медиа и без текста подпись не нужна; при наличии медиа оставляем хотя бы вотермарку.
    if not caption and has_media:
        caption = watermark()
    context.statistics.repository.record(
        "to_c",
        source=str(chat_id),
        keywords=detect_keywords(text, context.rules),
    )
    await _notify_subscribers(text, caption, messages, client, context, notify_state)
    try:
        if photos:
            with tempfile.TemporaryDirectory(prefix="trevoga-source-") as directory:
                watermarked_photos = []
                for photo in photos:
                    output = Path(directory) / f"watermarked-{photo.name}"
                    await apply_watermark(photo, output)
                    watermarked_photos.append(output)
                sent = await client.send_file(
                    context.settings.group_c,
                    watermarked_photos,
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
        context.moderation.schedule(_autocheck_message(client, context, sent_message.id, text))
    except Exception:
        logger.exception("Failed to publish source message %s", message.id)
