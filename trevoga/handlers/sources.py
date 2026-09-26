import logging
import re
import tempfile
from pathlib import Path

from telethon import events

from trevoga.handlers.context import HandlerContext
from trevoga.services.fix_service import CAPTION_LIMIT
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

_TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)(?:\s[^>]*)?>")
_VOID_TAGS = {"br", "hr", "img", "input", "meta", "link"}


def _close_open_tags(text: str) -> str:
    """Возвращает закрывающие теги для всех незакрытых HTML-тегов в text."""
    stack: list[str] = []
    for match in _TAG_RE.finditer(text):
        is_close, name = match.group(1) == "/", match.group(2).lower()
        if name in _VOID_TAGS:
            continue
        if is_close:
            for index in range(len(stack) - 1, -1, -1):
                if stack[index] == name:
                    del stack[index:]
                    break
        else:
            stack.append(name)
    return "".join(f"</{name}>" for name in reversed(stack))


def _truncate_caption(caption: str, limit: int = CAPTION_LIMIT) -> str:
    """Обрезает подпись до лимита Telegram, не разрывая HTML-теги."""
    if len(caption) <= limit:
        return caption
    budget = max(0, limit - 32)
    cut = caption[:budget]
    last_open = cut.rfind("<")
    if last_open > cut.rfind(">"):
        cut = cut[:last_open]
    return f"{cut.rstrip()}…{_close_open_tags(cut)}"


def register(client, context: HandlerContext):
    @client.on(events.NewMessage())
    async def forward_to_group_c(event):
        if event.chat_id not in context.source_channels:
            return
        # Album items also emit NewMessage events; the Album handler publishes them together.
        if event.message.grouped_id:
            return
        await _forward_messages([event.message], event.chat_id, client, context)

    @client.on(events.Album())
    async def forward_album_to_group_c(event):
        if event.chat_id not in context.source_channels:
            return
        await _forward_messages(event.messages, event.chat_id, client, context)

    @client.on(events.NewMessage(outgoing=True))
    async def fixme_message(event):
        """Режим .fixme: кажное исходящее сообщение в ЛЮБОМ чате правим через ИИ."""
        if not context.fixer or not context.fixer.fixme_enabled:
            return
        text = event.raw_text or ""
        if not text.strip() or text.lstrip().startswith((".", "/")):
            return
        fixed = await context.fixer.fixme_text(text)
        if not fixed:
            return
        try:
            await event.edit(fixed)
        except Exception:
            logger.exception("fixme edit failed")


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


async def _forward_messages(messages, chat_id, client, context: HandlerContext):
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
    media_caption = _truncate_caption(caption)
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
                    caption=media_caption,
                    parse_mode="html",
                    link_preview=False,
                )
        elif any(item.media for item in messages):
            sent = await client.send_file(
                context.settings.group_c,
                [item.media for item in messages if item.media],
                caption=media_caption,
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
