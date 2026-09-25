"""Тексты бота-подписчика (переиспользует строки из trevoga.i18n)."""

from trevoga.i18n import (
    SUB_ADDED,
    SUB_LIST,
    SUB_NONE,
    UNSUB_ALL,
    UNSUB_FORMAT,
    UNSUB_MISSING,
    UNSUB_REMOVED,
)

__all__ = [
    "SUB_ADDED",
    "SUB_LIST",
    "SUB_NONE",
    "UNSUB_ALL",
    "UNSUB_FORMAT",
    "UNSUB_MISSING",
    "UNSUB_REMOVED",
    "WELCOME",
    "HELP",
    "BTN_MY_SUBS",
    "BTN_HELP",
    "EMPTY_TEXT",
]

WELCOME = (
    "<blockquote>👋 Я бот сповіщень OpenTrevoga.\n\n"
    "Підпишіться на ключові слова — і я надсилатиму вам пости, "
    "де вони згадуються.\n\n"
    "Наприклад: <code>/sub бпла</code> або <code>/sub краматорськ</code>\n\n"
    "Команди:\n"
    "/sub СЛОВО — підписатися\n"
    "/sub — мої підписки\n"
    "/unsub СЛОВО — відписатися\n"
    "/unsub all — скинути всі\n"
    "/help — довідка</blockquote>"
)

HELP = (
    "<blockquote>=== КОМАНДИ ПІДПИСКИ ===\n\n"
    "/sub [СЛОВО] — підписатися на ключове слово\n"
    "/unsub [СЛОВО] — відписатися від ключового слова\n"
    "/unsub all — скинути всі підписки\n"
    "/help — ця довідка</blockquote>"
)

BTN_MY_SUBS = "📋 Мої підписки"
BTN_HELP = "❓ Довідка"

EMPTY_TEXT = "<blockquote>ℹ️ Напишіть ключове слово: <code>/sub бпла</code></blockquote>"
