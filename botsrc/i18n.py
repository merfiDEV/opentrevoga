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
    "BTN_SETTINGS",
    "SETTINGS_TITLE",
    "SETTINGS_PHOTO_ON",
    "SETTINGS_PHOTO_OFF",
    "SETTINGS_WIKI_ON",
    "SETTINGS_WIKI_OFF",
    "SETTINGS_DONE",
    "EMPTY_TEXT",
    "USERS_TITLE",
    "USERS_NO_KEYWORDS",
    "USERS_DENIED",
]

BTN_SETTINGS = "⚙️ Налаштування"

SETTINGS_TITLE = (
    "<blockquote>⚙️ <b>Налаштування підказок</b>\n\n"
    "Керуйте одразу всіма підказками: 📷 фото-картки та 🔗 посилання на Вікіпедію.\n"
    "Сам текст поста приходить завжди."
    "</blockquote>"
)
SETTINGS_PHOTO_ON = "✅ 📷 Фото-картки (усі)"
SETTINGS_PHOTO_OFF = "❌ 📷 Фото-картки (усі)"
SETTINGS_WIKI_ON = "✅ 🔗 Посилання на Вікіпедію (усі)"
SETTINGS_WIKI_OFF = "❌ 🔗 Посилання на Вікіпедію (усі)"
SETTINGS_DONE = "Готово ✅"

WELCOME = (
    "<blockquote>👋 Привіт! Я бот сповіщень OpenTrevoga.\n\n"
    "Я надсилаю сюди, в особисті повідомлення, пости за вашими ключовими словами — "
    "щойно вони з'являються в каналі.\n\n"
    "🔎 <b>Як це працює:</b>\n"
    "1. Ви обираєте слово — наприклад, місто чи тип озброєння.\n"
    "2. Я стежу за стрічкою постів.\n"
    "3. Коли в пості згадується ваше слово — я одразу надсилаю його вам.\n\n"
    "✅ <b>Приклади:</b>\n"
    "<code>/sub бпла</code> — усе про БПЛА та шахеди\n"
    "<code>/sub краматорськ</code> — новини по Краматорську\n"
    "<code>/sub каб</code> — про керовані авіабомби\n\n"
    "➡️ Підписуйтесь на кілька слів одразу — просто надішліть /sub для кожного.\n\n"
    "Подивитись підписки: /sub\n"
    "Відписатись: /unsub СЛОВО або /unsub all\n"
    "Довідка: /help</blockquote>"
)

HELP = (
    "<blockquote>❓ <b>Довідка</b>\n\n"
    "🔔 <b>Підписка на слово:</b>\n"
    "<code>/sub бпла</code> — підписатися на «бпла»\n"
    "<code>/sub краматорськ</code> — підписатися на «краматорськ»\n"
    "Можна підписатися на кілька слів — додавайте їх по одному.\n\n"
    "📋 <b>Переглянути свої підписки:</b>\n"
    "<code>/sub</code> — без слова показує список\n\n"
    "🗑 <b>Відписка:</b>\n"
    "<code>/unsub бпла</code> — прибрати «бпла»\n"
    "<code>/unsub all</code> — прибрати всі підписки\n\n"
    "💡 <b>Популярні слова:</b> бпла, шахед, каб, рсзв, fpv, ракета, балістика, арта, "
    "а також ваші міста (краматорськ, покровськ, бахмут тощо).\n\n"
    "Щойно в каналі з'явиться пост із вашим словом — я одразу надішлю його сюди.</blockquote>"
)

BTN_MY_SUBS = "📋 Мої підписки"
BTN_HELP = "❓ Довідка"

USERS_TITLE = "<blockquote>👥 <b>Статистика підписок</b>\n\nВсього користувачів: {users}\nВсього підписок: {subs}</blockquote>"
USERS_NO_KEYWORDS = "<blockquote>👥 Користувачів: {users}\n\nПідписок поки немає.</blockquote>"
USERS_DENIED = "<blockquote>⛔ Команда лише для адміністратора.</blockquote>"

EMPTY_TEXT = "<blockquote>ℹ️ Напишіть ключове слово: <code>/sub бпла</code></blockquote>"
