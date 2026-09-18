<div align="center">

# 🚨 Trevoga

**Telegram-бот для агрегації, AI-модерації та публікації новин**

**Зроблено в Україні 🇺🇦**

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Telethon](https://img.shields.io/badge/Telethon-1.44.0-2CA5E0?logo=telegram&logoColor=white)
![SQLite](https://img.shields.io/badge/DB-SQLite-003B57?logo=sqlite&logoColor=white)
![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/license-internal-lightgrey)

</div>

---

## 🇺🇦 Позиція

Цей проєкт створено **в Україні**. Я — автор — **максимально засуджую та ненавиджу росію** і все, що вона робить проти України.

Ці терористи **зруйнували мій дім і моє життя**. Вони забрали в мене все — але не змогли забрати мою ненависть до них і мою любов до України.

Слава Україні! Героям слава! 🇺🇦

> **росія — країна-терорист. Ніколи не пробачимо. Ніколи не забудемо.**

---

## 📖 Зміст

- [Про проєкт](#-про-проєкт)
- [Можливості](#-можливості)
- [Стек](#-стек)
- [Структура проєкту](#-структура-проєкту)
- [Встановлення](#-встановлення)
- [Налаштування](#-налаштування)
- [Запуск](#-запуск)
- [Команди адміністратора](#-команди-адміністратора)
- [Команди підписки](#-команди-підписки)
- [Тести](#-тести)

---

## 📌 Про проєкт

**Trevoga** — Telegram-бот на [Telethon](https://docs.telethon.dev/), який слухає канали-джерела, пересилає новини до службової групи модерації, а після схвалення (вручну або через AI) публікує їх у цільові групи та канали. Підтримує AI-редактуру тексту, водяні знаки, статистику та підписки на ключові слова.

## ✨ Можливості

| | Функція | Опис |
|---|---|---|
| 📥 | **Пересилання постів** | Слухає `SOURCE_CHANNELS` → службова група `GROUP_C` → цільові `GROUP_D_TARGETS` / `CHANNEL_TARGETS` |
| 🤖 | **AI-модерація** (`.ai`) | Перевірка корисності новини через OpenAI-сумісний API, авто-схвалення/відхилення |
| ✍️ | **AI-редактура** (`.fix`) | Переписування тексту в тонах: `short`, `urgent`, `official`, `neutral` |
| 🛡️ | **Модерація каналів** | Перезаливка постів адмінів з водяним знаком OpenTrevoga, видалення оригіналів |
| 🚫 | **Виключення каналів** (`.cignore`) | Канали, що не підлягають модерації |
| 💧 | **Водяний знак** (`.wmark`) | Увімк/вимк посилання в підписі постів |
| 📊 | **Статистика** (`.stats`) | Звіт щодо публікацій за період або загалом |
| 🔔 | **Підписки** (`.sub` / `.unsub`) | Сповіщення за ключовими словами |
| 💾 | **Сховище** | SQLite (`trevoga.db`): пости, статистика, модерація, підписки |

## 🧱 Стек

- **Python 3.11**
- [**Telethon**](https://docs.telethon.dev/) — MTProto клієнт Telegram
- **SQLite** — локальне сховище
- **httpx** — HTTP-клієнт для AI API
- **pytest** — тестування

## 🗂️ Структура проєкту

```
trevoga/
├── main.py                      # точка входу
├── config.py                    # зворотна сумісність (реекспорт налаштувань)
├── trevoga/
│   ├── app.py                   # ініціалізація та запуск бота
│   ├── config.py                # завантаження/збереження налаштувань з .env
│   ├── models.py                # моделі даних
│   ├── handlers/                # обробники подій Telethon
│   │   ├── commands.py          # адмін-команди (.ai, .fix, .stats, .wmark, .cignore, ...)
│   │   ├── sources.py           # прийом постів з джерел
│   │   ├── channel_moderation.py
│   │   ├── comments.py
│   │   └── reactions.py
│   ├── integrations/
│   │   ├── telegram.py          # створення Telethon-клієнта
│   │   └── ai_client.py         # клієнт AI API (модерація/фікс тексту)
│   ├── services/
│   │   ├── moderation.py        # логіка AI-модерації постів
│   │   ├── publishing.py        # публікація в цільові групи/канали
│   │   ├── statistics.py        # збір і побудова звітів
│   │   └── text_cleaner.py      # очищення тексту, водяний знак, HTML-форматування
│   └── storage/
│       ├── database.py          # ініціалізація SQLite
│       └── repositories.py      # репозиторії (пости, статистика, модерація, підписки)
├── tests/                        # pytest-тести
├── asseti/                       # зображення для типів постів
├── aianalyze.py                  # допоміжний скрипт аналізу
├── aifix.py                      # допоміжний скрипт AI-фіксу
└── requirements.txt
```

## ⚙️ Встановлення

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 🔧 Налаштування

Скопіюйте `.env.example` у `.env` та заповніть значення:

```bash
copy .env.example .env
```

<details>
<summary><b>📋 Змінні середовища</b> (натисніть, щоб розгорнути)</summary>

| Змінна | Опис |
|---|---|
| `API_ID`, `API_HASH` | Telegram API credentials ([my.telegram.org](https://my.telegram.org)) |
| `SOURCE_CHANNELS` | Джерела новин (username через кому) |
| `GROUP_C` | ID службової групи для модерації постів |
| `GROUP_D_TARGETS` | Цільові групи/чати для публікації |
| `CHANNEL_TARGETS` | Канали для прямої публікації (бот — адмін) |
| `ADMIN_IDS` | Telegram user id адміністраторів бота |
| `AI_MODE`, `AI_API_BASE`, `AI_MODEL`, `AI_API_KEY` | Налаштування AI-модерації |
| `AI_FIX_*` | Окремі налаштування для `.fix` (за замовчуванням успадковуються від `AI_*`) |
| `CHANNEL_MODERATION_ENABLED`, `CIGNORE_CHANNELS` | Модерація каналів адмінів і виключення |
| `DATABASE_FILE_NAME`, `SESSION_FILE_NAME` | Імена файлів SQLite та Telethon-сесії |

Повний список — див. `.env.example`.

</details>

## 🚀 Запуск

```bash
python main.py
```

При першому запуску Telethon запросить авторизацію (номер телефону / код), після чого створить файл сесії.

## 🛠️ Команди адміністратора

> Виконуються у службовій групі `GROUP_C`

| Команда | Дія |
|---|---|
| `.ai` / `.ai on` / `.ai off` / `.ai status` | Керування AI-модерацією |
| `.ai set [MODEL]` | Зміна моделі AI |
| `.wmark` / `.wmark on` / `.wmark off` | Водяний знак у підписі |
| `.cignore [ID/@name]` / `.cignore off` / `.cignore list` | Виключення каналів |
| `.fix [short\|urgent\|official\|neutral]` | AI-редактура тексту |
| `.stats` / `.stats 12` / `.stats 24` | Статистика публікацій |
| `.ai_reason [MESSAGE_ID]` | Причина рішення AI щодо поста |
| `.отмена` / `.delete` / `.удалить` | Скасування/видалення поста |
| `.help` | Список команд |

## 🔔 Команди підписки

| Команда | Дія |
|---|---|
| `.sub [СЛОВО]` | Підписатися на ключове слово |
| `.unsub [СЛОВО]` | Відписатися від ключового слова |
| `.unsub all` | Скинути всі підписки |

## 🧪 Тести

```bash
pytest
```

---

<div align="center">

Слава Україні! Героям слава! 🇺🇦

</div>
