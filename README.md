<div align="center">

# 🚨 Trevoga

**Telegram-бот для агрегации, AI-модерации и публикации новостей**

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Telethon](https://img.shields.io/badge/Telethon-1.44.0-2CA5E0?logo=telegram&logoColor=white)
![SQLite](https://img.shields.io/badge/DB-SQLite-003B57?logo=sqlite&logoColor=white)
![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/license-internal-lightgrey)

</div>

---

## 📖 Оглавление

- [О проекте](#-о-проекте)
- [Возможности](#-возможности)
- [Стек](#-стек)
- [Структура проекта](#-структура-проекта)
- [Установка](#-установка)
- [Настройка](#-настройка)
- [Запуск](#-запуск)
- [Команды администратора](#-команды-администратора)
- [Команды подписки](#-команды-подписки)
- [Тесты](#-тесты)

---

## 📌 О проекте

**Trevoga** — Telegram-бот на [Telethon](https://docs.telethon.dev/), который слушает каналы-источники, пересылает новости в служебную группу модерации, а после одобрения (вручную или через AI) публикует их в целевые группы и каналы. Поддерживает AI-редактуру текста, водяные знаки, статистику и подписки на ключевые слова.

## ✨ Возможности

| | Функция | Описание |
|---|---|---|
| 📥 | **Пересылка постов** | Слушает `SOURCE_CHANNELS` → служебная группа `GROUP_C` → целевые `GROUP_D_TARGETS` / `CHANNEL_TARGETS` |
| 🤖 | **AI-модерация** (`.ai`) | Проверка полезности новости через OpenAI-совместимый API, авто-одобрение/отклонение |
| ✍️ | **AI-редактура** (`.fix`) | Переписывание текста в тонах: `short`, `urgent`, `official`, `neutral` |
| 🛡️ | **Модерация каналов** | Перезаливка постов админов с водяным знаком OpenTrevoga, удаление оригиналов |
| 🚫 | **Исключения каналов** (`.cignore`) | Каналы, не подлежащие модерации |
| 💧 | **Водяной знак** (`.wmark`) | Вкл/выкл ссылки в подписи постов |
| 📊 | **Статистика** (`.stats`) | Отчёт по публикациям за период или в целом |
| 🔔 | **Подписки** (`.sub` / `.unsub`) | Уведомления по ключевым словам |
| 💾 | **Хранилище** | SQLite (`trevoga.db`): посты, статистика, модерация, подписки |

## 🧱 Стек

- **Python 3.11**
- [**Telethon**](https://docs.telethon.dev/) — MTProto клиент Telegram
- **SQLite** — локальное хранилище
- **httpx** — HTTP-клиент для AI API
- **pytest** — тестирование

## 🗂️ Структура проекта

```
trevoga/
├── main.py                      # точка входа
├── config.py                    # обратная совместимость (реэкспорт настроек)
├── trevoga/
│   ├── app.py                   # инициализация и запуск бота
│   ├── config.py                # загрузка/сохранение настроек из .env
│   ├── models.py                # модели данных
│   ├── handlers/                # обработчики событий Telethon
│   │   ├── commands.py          # админ-команды (.ai, .fix, .stats, .wmark, .cignore, ...)
│   │   ├── sources.py           # приём постов из источников
│   │   ├── channel_moderation.py
│   │   ├── comments.py
│   │   └── reactions.py
│   ├── integrations/
│   │   ├── telegram.py          # создание Telethon-клиента
│   │   └── ai_client.py         # клиент AI API (модерация/фикс текста)
│   ├── services/
│   │   ├── moderation.py        # логика AI-модерации постов
│   │   ├── publishing.py        # публикация в целевые группы/каналы
│   │   ├── statistics.py        # сбор и построение отчётов
│   │   └── text_cleaner.py      # очистка текста, водяной знак, HTML-форматирование
│   └── storage/
│       ├── database.py          # инициализация SQLite
│       └── repositories.py      # репозитории (посты, статистика, модерация, подписки)
├── tests/                        # pytest-тесты
├── asseti/                       # изображения для типов постов
├── aianalyze.py                  # вспомогательный скрипт анализа
├── aifix.py                      # вспомогательный скрипт AI-фикса
└── requirements.txt
```

## ⚙️ Установка

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 🔧 Настройка

Скопируйте `.env.example` в `.env` и заполните значения:

```bash
copy .env.example .env
```

<details>
<summary><b>📋 Переменные окружения</b> (нажмите, чтобы развернуть)</summary>

| Переменная | Описание |
|---|---|
| `API_ID`, `API_HASH` | Telegram API credentials ([my.telegram.org](https://my.telegram.org)) |
| `SOURCE_CHANNELS` | Источники новостей (username через запятую) |
| `GROUP_C` | ID служебной группы для модерации постов |
| `GROUP_D_TARGETS` | Целевые группы/чаты для публикации |
| `CHANNEL_TARGETS` | Каналы для прямой публикации (бот — админ) |
| `ADMIN_IDS` | Telegram user id администраторов бота |
| `AI_MODE`, `AI_API_BASE`, `AI_MODEL`, `AI_API_KEY` | Настройки AI-модерации |
| `AI_FIX_*` | Отдельные настройки для `.fix` (по умолчанию наследуются от `AI_*`) |
| `CHANNEL_MODERATION_ENABLED`, `CIGNORE_CHANNELS` | Модерация каналов админов и исключения |
| `DATABASE_FILE_NAME`, `SESSION_FILE_NAME` | Имена файлов SQLite и Telethon-сессии |

Полный список — см. `.env.example`.

</details>

## 🚀 Запуск

```bash
python main.py
```

При первом запуске Telethon запросит авторизацию (номер телефона / код), после чего создаст файл сессии.

## 🛠️ Команды администратора

> Выполняются в служебной группе `GROUP_C`

| Команда | Действие |
|---|---|
| `.ai` / `.ai on` / `.ai off` / `.ai status` | Управление AI-модерацией |
| `.ai set [MODEL]` | Смена модели AI |
| `.wmark` / `.wmark on` / `.wmark off` | Водяной знак в подписи |
| `.cignore [ID/@name]` / `.cignore off` / `.cignore list` | Исключения каналов |
| `.fix [short\|urgent\|official\|neutral]` | AI-редактура текста |
| `.stats` / `.stats 12` / `.stats 24` | Статистика публикаций |
| `.ai_reason [MESSAGE_ID]` | Причина решения AI по посту |
| `.отмена` / `.delete` / `.удалить` | Отмена/удаление поста |
| `.help` | Список команд |

## 🔔 Команды подписки

| Команда | Действие |
|---|---|
| `.sub [СЛОВО]` | Подписаться на ключевое слово |
| `.unsub [СЛОВО]` | Отписаться от ключевого слова |
| `.unsub all` | Сбросить все подписки |

## 🧪 Тесты

```bash
pytest
```

---

<div align="center">

Сделано для **OpenTrevoga** 🇺🇦

</div>
