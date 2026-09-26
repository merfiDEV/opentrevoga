"""Telegram-бот подписок: ЛС-команды /sub, /unsub и рассылка постов канала."""

import asyncio
import html
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from botsrc import i18n
from botsrc.broadcast import Broadcaster
from botsrc.config import BotSettings
from botsrc.map_service import render_map_photo, shutdown_map_renderer
from botsrc.storage import SubscriptionStore


logger = logging.getLogger(__name__)


def _menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=i18n.BTN_MY_SUBS)],
            [KeyboardButton(text=i18n.BTN_MAP)],
            [KeyboardButton(text=i18n.BTN_SETTINGS)],
            [KeyboardButton(text=i18n.BTN_HOW)],
            [KeyboardButton(text=i18n.BTN_SUGGEST)],
            [KeyboardButton(text=i18n.BTN_HELP)],
        ],
        resize_keyboard=True,
    )


def _start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=i18n.BTN_HOW, callback_data="info:how")],
            [InlineKeyboardButton(text=i18n.BTN_SUGGEST, url=i18n.DEVELOPER_CONTACT)],
        ]
    )


def _settings_keyboard(photo_on: bool, wiki_on: bool) -> InlineKeyboardMarkup:
    photo_text = i18n.SETTINGS_PHOTO_ON if photo_on else i18n.SETTINGS_PHOTO_OFF
    wiki_text = i18n.SETTINGS_WIKI_ON if wiki_on else i18n.SETTINGS_WIKI_OFF
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=photo_text, callback_data="hint:toggle:photo")],
            [InlineKeyboardButton(text=wiki_text, callback_data="hint:toggle:wiki")],
            [InlineKeyboardButton(text=i18n.SETTINGS_DONE, callback_data="hint:done")],
        ]
    )


def _parse_command(text: str, name: str) -> str | None:
    """Возвращает аргумент команды /name, или None если это не эта команда."""
    stripped = text.strip()
    prefix = f"/{name}"
    if not stripped.lower().startswith(prefix):
        return None
    rest = stripped[len(prefix) :]
    # Допускаем /sub@BotName — отсекаем упоминание бота.
    if rest.startswith("@"):
        parts = rest.split(maxsplit=1)
        rest = parts[1] if len(parts) > 1 else ""
    if rest and not rest[0].isspace():
        return None
    return rest.strip()


def _is_command(message: Message) -> bool:
    """True, если сообщение — команда (/что-угодно), чтобы не съедать её рассылкой."""
    text = message.text or message.caption or ""
    return text.lstrip().startswith("/")


def _subscriptions_text(store: SubscriptionStore, user_id: int) -> str:
    keywords = store.list_for_user(user_id)
    return i18n.SUB_LIST.format(
        keywords=", ".join(html.escape(word) for word in keywords) if keywords else i18n.SUB_NONE
    )


class SubscriberBot:
    def __init__(self, settings: BotSettings):
        self.settings = settings
        self.store = SubscriptionStore(settings.database_path)
        self.bot = Bot(
            token=settings.token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dispatcher = Dispatcher()
        self.broadcaster = Broadcaster(self.bot, self.store, settings.group_c)
        self._register()

    def _register(self) -> None:
        dp = self.dispatcher
        dp.channel_post.register(self.on_channel_post)

        # ВАЖЛИВО: командные хендлеры реєструємо ПЕРЕД on_group_post, щоб
        # /map (та інші команди) у GROUP_C не «з'їдались» розсилкою постів.
        dp.message.register(self.cmd_map, Command("map"))
        dp.message.register(self.cmd_start, Command("start", "help"))
        dp.message.register(self.on_sub, Command("sub"))
        dp.message.register(self.on_unsub, Command("unsub"))
        dp.message.register(self.on_settings, Command("settings"))
        dp.message.register(self.cmd_users, Command("users"))

        # Решта повідомлень GROUP_C — це пости для розсилки.
        dp.message.register(self.on_group_post, F.chat.id == self.settings.group_c)

        dp.message.register(
            self.on_menu_button,
            F.text.in_(
                {
                    i18n.BTN_MY_SUBS,
                    i18n.BTN_SETTINGS,
                    i18n.BTN_HELP,
                    i18n.BTN_HOW,
                    i18n.BTN_SUGGEST,
                }
            ),
        )
        dp.callback_query.register(self.on_settings_toggle, F.data.startswith("hint:toggle:"))
        dp.callback_query.register(self.on_settings_done, F.data == "hint:done")
        dp.callback_query.register(self.on_info_how, F.data == "info:how")

    async def cmd_start(self, message: Message) -> None:
        await message.answer(i18n.WELCOME, reply_markup=_menu())
        await message.answer(i18n.START_MENU_HINT, reply_markup=_start_keyboard())

    async def on_info_how(self, callback: CallbackQuery) -> None:
        await callback.message.answer(i18n.HOW_IT_WORKS)
        await callback.answer()

    async def on_menu_button(self, message: Message) -> None:
            if message.text == i18n.BTN_MY_SUBS:
                await message.answer(self.subscriptions(message.from_user.id), reply_markup=_menu())
            elif message.text == i18n.BTN_MAP:
                await self.cmd_map(message)
            elif message.text == i18n.BTN_SETTINGS:
                await self.on_settings(message)
            elif message.text == i18n.BTN_HOW:
                await message.answer(i18n.HOW_IT_WORKS, reply_markup=_menu())
            elif message.text == i18n.BTN_SUGGEST:
                await message.answer(i18n.SUGGEST_TEXT, reply_markup=_menu())
            else:
                await message.answer(i18n.HELP, reply_markup=_menu())

    async def on_settings(self, message: Message) -> None:
        photo_on, wiki_on = self.store.hint_settings(message.from_user.id)
        await message.answer(
            i18n.SETTINGS_TITLE,
            reply_markup=_settings_keyboard(photo_on, wiki_on),
        )

    async def on_settings_toggle(self, callback: CallbackQuery) -> None:
        _, _, kind = callback.data.split(":", 2)
        user_id = callback.from_user.id
        photo_on, wiki_on = self.store.hint_settings(user_id)
        if kind == "photo":
            photo_on = not photo_on
        else:
            wiki_on = not wiki_on
        self.store.set_hint_settings(user_id, photo_on, wiki_on)
        await callback.message.edit_reply_markup(reply_markup=_settings_keyboard(photo_on, wiki_on))
        await callback.answer()

    async def on_settings_done(self, callback: CallbackQuery) -> None:
        await callback.message.delete()
        await callback.answer()

    async def on_sub(self, message: Message) -> None:
        value = _parse_command(message.text, "sub")
        if value is None:
            return
        if not value:
            await message.answer(self.subscriptions(message.from_user.id))
            return
        normalized = value.lower()
        self.store.add(message.from_user.id, normalized)
        await message.answer(i18n.SUB_ADDED.format(word=html.escape(normalized)))

    async def on_unsub(self, message: Message) -> None:
        value = _parse_command(message.text, "unsub")
        if value is None:
            return
        if not value:
            await message.answer(i18n.UNSUB_FORMAT)
            return
        if value.lower() == "all":
            removed = self.store.remove_all(message.from_user.id)
            await message.answer(i18n.UNSUB_ALL.format(count=removed))
            return
        normalized = value.lower()
        if self.store.remove(message.from_user.id, normalized):
            await message.answer(i18n.UNSUB_REMOVED.format(word=html.escape(normalized)))
        else:
            await message.answer(i18n.UNSUB_MISSING.format(word=html.escape(normalized)))

    async def cmd_users(self, message: Message) -> None:
        if message.from_user.id not in self.settings.admin_ids:
            await message.answer(i18n.USERS_DENIED)
            return
        users = self.store.user_count()
        keywords = self.store.keyword_stats()
        if not keywords:
            await message.answer(i18n.USERS_NO_KEYWORDS.format(users=users))
            return
        lines = "\n".join(f"• {html.escape(word)} — {count}" for word, count in keywords)
        await message.answer(
            i18n.USERS_TITLE.format(users=users, subs=self.store.total_subscriptions())
            + f"<blockquote>{lines}</blockquote>"
        )

    def subscriptions(self, user_id: int) -> str:
        return _subscriptions_text(self.store, user_id)

    async def cmd_map(self, message: Message) -> None:
        """Надіслати карту повітряних тривог. Працює в будь-якому чаті."""
        notice = await message.answer(i18n.MAP_RENDERING)
        try:
            photo = await render_map_photo()
        except Exception:
            logger.exception("Failed to render alert map")
            await message.answer(i18n.MAP_FAILED)
            return
        finally:
            try:
                await notice.delete()
            except Exception:
                pass
        await message.answer_photo(
            BufferedInputFile(photo, filename="map.jpg"),
            caption=i18n.MAP_CAPTION,
        )

    async def on_channel_post(self, message: Message) -> None:
        await self.broadcaster.handle_channel_post(message)

    async def on_group_post(self, message: Message) -> None:
        # GROUP_C — супергруппа, поэтому посты приходят в message, а не в channel_post.
        # Команды сюда не попадают: они перехвачены выше по регистрации.
        if _is_command(message):
            return
        await self.broadcaster.handle_channel_post(message)

    async def run(self) -> None:
            self.broadcaster.attach_loop(asyncio.get_running_loop())
            await self.bot.delete_webhook(drop_pending_updates=True)
            try:
                await self.dispatcher.start_polling(self.bot)
            finally:
                await shutdown_map_renderer()


async def run_bot(settings: BotSettings) -> None:
    await SubscriberBot(settings).run()