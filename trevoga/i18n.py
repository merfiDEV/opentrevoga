"""Єдина точка зберігання всіх текстових рядків бота (українською)."""

# --- Довідка ---
HELP_USER = """<blockquote>=== ПІДПИСКИ ===

Керування підписками перенесено в окремий бот: @OpenTrevogabot
Напишіть йому /sub [СЛОВО] у приватних повідомленнях.</blockquote>"""

HELP_ADMIN = """<blockquote>=== КОМАНДИ АДМІНІСТРАТОРА ===

.ai | .ai on | .ai off | .ai status | .ai set [MODEL]
.wmark | .wmark on | .wmark off
.aicheck | .aicheck on | .aicheck off
.cignore [ID or @name] | .cignore off | .cignore list
.addchannel add|del|list [ID or @name]
.fix [short|urgent|official|neutral] | .fix test | .fix <прохання> | .fix undo | .fix help
.stats | .stats 12 | .stats 24
.ai_reason [MESSAGE_ID] або відповіддю на повідомлення
.health — стан бота (uptime, AI, БД, FloodWait, остання помилка)
.відміна | .delete | .видалити
.help

=== ПІДПИСКИ ===

Керування підписками перенесено в окремий бот: @OpenTrevogabot
Напишіть йому /sub [СЛОВО] у приватних повідомленнях.</blockquote>"""

FIX_HELP = """<blockquote>=== .fix ===
.fix — відредагувати відповіддю (режим default)
.fix short|urgent|official|neutral — стиль редагування
.fix test [режим] [прохання] — показати результат, не змінюючи пост
.fix [прохання] — власна інструкція редактору (напр. «прибери мат»)
.fix undo — повернути початковий текст (протягом 10 хвилин)
.fix help — ця довідка</blockquote>"""

# --- .fix ---
FIX_NEED_REPLY_UNDO = (
    "<blockquote>⚠️ Дайте відповідь .fix undo на відредаговане повідомлення.</blockquote>"
)
FIX_UNDO_MISSING = (
    "<blockquote>ℹ️ Немає збереженої версії для відкату (або минув термін).</blockquote>"
)
FIX_UNDO_DONE = "<blockquote>↩️ Відновлено початковий текст.</blockquote>"
FIX_UNDO_FAILED = "<blockquote>⚠️ Не вдалося відкотити: {error}</blockquote>"
FIX_AI_UNAVAILABLE = "<blockquote>⚠️ AI-редактор недоступний{detail}</blockquote>"
FIX_UNCHANGED = "<blockquote>ℹ️ Текст уже гаразд, змін немає.</blockquote>"
FIX_TOO_LONG = "<blockquote>⚠️ Результат задовгий для цього повідомлення.</blockquote>"
FIX_OVERFLOW = "<blockquote>⚠️ Результат не вміщується в ліміт повідомлення ({length}/{limit}). Спробуйте .fix test.</blockquote>"
FIX_PREVIEW = "<blockquote>🔎 Попередній перегляд ({mode}):</blockquote>{body}"
FIX_EDIT_FAILED = "<blockquote>⚠️ Не вдалося змінити пост: {error}</blockquote>"
FIX_DONE = "<blockquote>✅ Виправлено (режим: {mode})</blockquote>"
FIX_NEED_REPLY = "<blockquote>⚠️ Дайте відповідь командою .fix на повідомлення, яке потрібно відредагувати.</blockquote>"
FIX_NO_SOURCE = "<blockquote>⚠️ Не вдалося отримати початкове повідомлення.</blockquote>"

# --- .cignore ---
CIGNORE_LIST = "Ігноровані канали: {channels}"
CIGNORE_NONE = "немає"
CIGNORE_OFF = "Ігнорування каналів вимкнено"
CIGNORE_ADDED = "Канал додано до виключень: {channel_id}"
CIGNORE_NOT_FOUND = "Не вдалося знайти канал: {error}"

# --- .ai ---
AI_NO_MODELS = "<blockquote>Доступні моделі не знайдено</blockquote>"
AI_MODELS_LIST = "<blockquote>Доступні моделі:\n{models}</blockquote>"
AI_SET_FORMAT = "<blockquote>Формат: .ai set MODEL [fix]</blockquote>"
AI_MODEL_CHANGED = "<blockquote>Модель {scope} змінено на: {model}</blockquote>"
AI_MODEL_UNKNOWN = "<blockquote>Такої моделі немає в списку доступних</blockquote>"
AI_MODELS_FAILED = "<blockquote>Не вдалося отримати моделі: {error}</blockquote>"
AI_ENABLE_FAILED = "<blockquote>AI не увімкнено: {error}</blockquote>"

# --- .wmark ---
WMARK_ON = "<blockquote>Посилання у ватермарці: увімкнено ✅</blockquote>"
WMARK_OFF = "<blockquote>Посилання у ватермарці: вимкнено ❌</blockquote>"

# --- .cart ---
CART_ON = "<blockquote>Фото-картки озброєнь: увімкнено ✅</blockquote>"
CART_OFF = "<blockquote>Фото-картки озброєнь: вимкнено ❌</blockquote>"

# --- .aicheck ---
AICHECK_ON = "<blockquote>AI-редактор (official): увімкнено ✅</blockquote>"
AICHECK_OFF = "<blockquote>AI-редактор (official): вимкнено ❌</blockquote>"

# --- .sub / .unsub ---
SUB_LIST = "<blockquote>📋 Ваші підписки: {keywords}\n\n➕ Додати ще: /sub СЛОВО\n🗑 Прибрати: /unsub СЛОВО або /unsub all\n\n📌 Можна підписуватися на типи озброєння (бпла, каб, рсзв, fpv, ракета, балістика, арта) або на своє місто (краматорськ, покровськ, бахмут тощо)</blockquote>"
SUB_NONE = "немає"
SUB_ADDED = "<blockquote>Підписку на «{word}» додано</blockquote>"
UNSUB_FORMAT = "<blockquote>Формат: .unsub СЛОВО | .unsub all</blockquote>"
UNSUB_ALL = "<blockquote>Скинуто підписок: {count}</blockquote>"
UNSUB_REMOVED = "<blockquote>Підписку на «{word}» видалено</blockquote>"
UNSUB_MISSING = "<blockquote>Підписку на «{word}» не знайдено</blockquote>"

# --- .health ---
HEALTH_TEXT = (
    "<blockquote>🩺 Стан бота\n\n"
    "⏱ Uptime: {uptime}\n"
    "🤖 AI: {ai_status}\n"
    "🌊 FloodWait: {floodwait}\n"
    "💾 БД: {db_size}\n"
    "🕒 Остання помилка: {last_error}</blockquote>"
)
HEALTH_AI_OK = "доступний ✅"
HEALTH_AI_DOWN = "недоступний ❌ ({error})"
HEALTH_NO_ERROR = "немає"
HEALTH_DB_MISSING = "немає"

# --- .addchannel ---
ADDCHAN_FORMAT = "<blockquote>Формат: .addchannel add|del|list [ID або @name]</blockquote>"
ADDCHAN_LIST = "<blockquote>Канали-джерела: {channels}</blockquote>"
ADDCHAN_NONE = "немає"
ADDCHAN_ADDED = "<blockquote>✅ Канал додано до відстеження: {channel_id}</blockquote>"
ADDCHAN_REMOVED = "<blockquote>🗑 Канал прибрано з відстеження: {channel_id}</blockquote>"
ADDCHAN_MISSING = "<blockquote>ℹ️ Канал не знайдено серед відстежуваних: {channel_id}</blockquote>"
ADDCHAN_NOT_FOUND = "<blockquote>⚠️ Не вдалося знайти канал: {error}</blockquote>"

# --- .ai_reason ---
AI_REASON_MISSING = "<blockquote>Результат AI-перевірки не знайдено</blockquote>"
AI_REASON_TEXT = "<blockquote>Повідомлення: {message_id}\nСтатус: {status}\nПричина: {reason}\nПояснення: {reason_text}\nВпевненість: {confidence}</blockquote>"
