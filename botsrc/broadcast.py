"""Рассылка постов из GROUP_C подписчикам от имени бота."""

import asyncio
import html
import logging
import re
from pathlib import Path

from aiogram import Bot
from aiogram.types import InputMediaPhoto, InputMediaVideo, LinkPreviewOptions

from botsrc.storage import SubscriptionStore
from trevoga.services.text_cleaner import photo_rules

logger = logging.getLogger(__name__)

# Дедуп: не слать одно и то же ключевое слово чаще, чем раз в N секунд.
SUBSCRIBE_DEDUP_SECONDS = 10
SUBSCRIBE_MAX_TEXT_LENGTH = 250

# Задержка сбора альбома (media group) перед отправкой.
ALBUM_DEBOUNCE_SECONDS = 1.5

_TAG_RE = re.compile(r"<[^>]+>")

# Транслитерация укр/рос → латиница. Обе стороны (keyword и текст поста)
# приводятся к единой латинской форме, чтобы 'odesa' == 'одеса',
# 'izmail' == 'ізмаїл' / 'измаил'. Сравнение идёт по lowercase.
_TRANSLIT = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "ґ": "g",
        "д": "d",
        "е": "e",
        "є": "ie",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "і": "i",
        "ї": "i",
        "й": "i",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "iu",
        "я": "ia",
        "’": "",
        "'": "",
    }
)


def fold_homoglyphs(text: str) -> str:
    """Приводит текст к латинской форме для сравнения ключевых слов.

    Транслитерирует кириллицу, оставляя латиницу как есть, чтобы подписки
    в любой раскладке ('odesa' и 'одеса') совпадали.
    """
    return text.lower().translate(_TRANSLIT)


# Лейблы подсказок-карточек (label, wiki-url) — из photo_rules юзербота.
_CARD_RULES = [(label, url) for _keywords, _path, label, url in photo_rules(Path(".")) if url]


def card_label(message) -> str | None:
    """Возвращает label карточки, если сообщение содержит её wiki-ссылку."""
    text = message.html_text or message.caption or message.text or ""
    if not text:
        return None
    for label, url in _CARD_RULES:
        if url in text:
            return label
    return None


def _card_link(url: str, label: str) -> str:
    """HTML-ссылка на Википедию такой же формы, как в label_links юзербота."""
    return f'<a href="{url}">{label}</a>'


def strip_card_links(caption: str, label: str | None) -> str:
    """Убирает из caption строки со ссылкой подсказки (сам текст поста остаётся)."""
    if not caption or not label:
        return caption
    urls = [url for rule_label, url in _CARD_RULES if rule_label == label]
    if not urls:
        return caption
    kept = []
    for line in caption.splitlines():
        if any(_card_link(url, label) in line for url in urls):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _plain_text(message) -> str:
    """HTML-текст сообщения канала без тегов."""
    raw = message.text or message.caption or ""
    return html.unescape(_TAG_RE.sub("", raw)).strip()


def _html_text(message) -> str:
    """Оригинальный HTML-текст сообщения (для отправки подписчику)."""
    return message.html_text or message.caption or ""


class Broadcaster:
    """Слушает посты канала и рассылает их подписчикам по ключевым словам."""

    def __init__(self, bot: Bot, store: SubscriptionStore, group_c: int):
        self.bot = bot
        self.store = store
        self.group_c = group_c
        self._notify_state: dict[str, float] = {}
        self._albums: dict[str, list] = {}
        self._album_tasks: dict[str, asyncio.Task] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def handle_channel_post(self, message) -> None:
        """Точка входа из хендлера aiogram (channel_post)."""
        if message.chat.id != self.group_c:
            return
        if message.media_group_id:
            self._buffer_album(message)
            return
        await self._dispatch([message])

    def _buffer_album(self, message) -> None:
        group_id = message.media_group_id
        self._albums.setdefault(group_id, []).append(message)
        existing = self._album_tasks.get(group_id)
        if existing:
            existing.cancel()
        self._album_tasks[group_id] = asyncio.create_task(self._flush_album_later(group_id))

    async def _flush_album_later(self, group_id: str) -> None:
        try:
            await asyncio.sleep(ALBUM_DEBOUNCE_SECONDS)
        except asyncio.CancelledError:
            return
        messages = self._albums.pop(group_id, [])
        self._album_tasks.pop(group_id, None)
        if messages:
            messages.sort(key=lambda item: item.message_id)
            await self._dispatch(messages)

    async def _dispatch(self, messages: list) -> None:
        text = _plain_text(messages[0])
        if not text:
            return
        if len(text) > SUBSCRIBE_MAX_TEXT_LENGTH:
            return
        lowered = fold_homoglyphs(text)
        matched = [
            keyword for keyword in self.store.all_keywords() if fold_homoglyphs(keyword) in lowered
        ]
        if not matched:
            return

        loop = asyncio.get_running_loop()
        now = loop.time()
        targets: set[int] = set()
        for keyword in matched:
            last_sent = self._notify_state.get(keyword)
            if last_sent is not None and now - last_sent < SUBSCRIBE_DEDUP_SECONDS:
                continue
            self._notify_state[keyword] = now
            targets.update(self.store.find_by_keyword(keyword))
        if not targets:
            return

        for user_id in targets:
            try:
                await self._send_to_user(user_id, messages)
            except Exception:
                logger.exception("Failed to notify subscriber %s", user_id)

    def _mute_flags(self, user_id: int, messages: list) -> tuple[str | None, bool, bool]:
        """Возвращает (label, photo_off, wiki_off) для сообщения и пользователя."""
        label = card_label(messages[0])
        if not label:
            return None, False, False
        photo_on, wiki_on = self.store.hint_settings(user_id)
        return label, not photo_on, not wiki_on

    async def _send_to_user(self, user_id: int, messages: list) -> None:
        caption = _html_text(messages[0])
        no_preview = LinkPreviewOptions(is_disabled=True)
        label, photo_off, wiki_off = self._mute_flags(user_id, messages)
        if label and wiki_off:
            caption = strip_card_links(caption, label)
        if label and photo_off:
            await self.bot.send_message(
                user_id,
                caption or _plain_text(messages[0]),
                parse_mode="HTML",
                link_preview_options=no_preview,
            )
            return
        if len(messages) == 1:
            message = messages[0]
            if message.photo:
                await self.bot.send_photo(
                    user_id,
                    message.photo[-1].file_id,
                    caption=caption,
                    parse_mode="HTML",
                )
            elif message.video:
                await self.bot.send_video(
                    user_id,
                    message.video.file_id,
                    caption=caption,
                    parse_mode="HTML",
                )
            elif message.document:
                await self.bot.send_document(
                    user_id,
                    message.document.file_id,
                    caption=caption,
                    parse_mode="HTML",
                )
            else:
                await self.bot.send_message(
                    user_id,
                    caption or _plain_text(message),
                    parse_mode="HTML",
                    link_preview_options=no_preview,
                )
            return

        media = []
        for index, message in enumerate(messages):
            item_caption = caption if index == 0 else None
            if message.photo:
                media.append(
                    InputMediaPhoto(
                        media=message.photo[-1].file_id,
                        caption=item_caption,
                        parse_mode="HTML",
                    )
                )
            elif message.video:
                media.append(
                    InputMediaVideo(
                        media=message.video.file_id,
                        caption=item_caption,
                        parse_mode="HTML",
                    )
                )
        if media:
            await self.bot.send_media_group(user_id, media=media)
        else:
            await self.bot.send_message(user_id, caption, parse_mode="HTML")
