import asyncio
import os
import re
import uuid

import httpx
from dotenv import load_dotenv

load_dotenv()


def _env_flag(name, default="0"):
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _env_float(name, default):
    try:
        return float(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


AI_MODE = _env_flag("AI_MODE")
AI_API_BASE = os.getenv("AI_API_BASE", "http://127.0.0.1:8000/v1").rstrip("/")
AI_MODEL = os.getenv("AI_MODEL", "deepseek-v4-flash")
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_CHECK_DELAY = _env_float("AI_CHECK_DELAY", 5.0)
AI_TIMEOUT = _env_float("AI_TIMEOUT", 60.0)

AI_MARK = "✅ Новина перевірена ШІ на корисність"

SYSTEM_PROMPT = (
    "Ты — строгий фильтр новостей. Тебе дан текст поста из Telegram. "
    "Определи, полезна ли эта новость жителям Донецкой области и переселенцам (ВПО). "
    "Полезная новость: атаки БПЛА, ракет, КАБ, обстрелы, воздушная тревога, "
    "эвакуация, укрытия и приюты, вода, электричество, газ, отопление, транспорт, "
    "выплаты, документы, медицина, работа служб и важные официальные объявления. "
    "Бесполезная новость: реклама, флуд, слухи без деталей, развлечения, спорт, "
    "политика без местной практической пользы. "
    "Ответь СТРОГО одним словом: ДА — если новость полезная, НЕТ — если бесполезная. "
    "Пояснения, знаки препинания и любые другие слова запрещены."
)

_YES_RE = re.compile(r"\b(ДА|ТАК|YES|TRUE)\b")
_NO_RE = re.compile(r"\b(НЕТ|НІ|NO|FALSE)\b")

_client = None
_chat_id = None
_is_forwarded = None
_forward = None
_enabled = AI_MODE


def setup(client, chat_id, is_forwarded, forward):
    global _client, _chat_id, _is_forwarded, _forward
    _client = client
    _chat_id = chat_id
    _is_forwarded = is_forwarded
    _forward = forward


def is_enabled():
    return _enabled


def set_enabled(value):
    global _enabled
    _enabled = bool(value)


def status_text():
    state = "увімкнено ✅" if _enabled else "вимкнено ❌"
    return f"<blockquote>🤖 AI режим: {state}</blockquote>"


def _parse_verdict(content):
    cleaned = (content or "").strip().upper()
    if not cleaned:
        return False
    if _NO_RE.search(cleaned):
        return False
    return bool(_YES_RE.search(cleaned))


async def ask_ai(text):
    headers = {}
    if AI_API_KEY:
        headers["Authorization"] = f"Bearer {AI_API_KEY}"
    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "stream": False,
        "temperature": 0,
        "user": uuid.uuid4().hex,
    }
    async with httpx.AsyncClient(timeout=AI_TIMEOUT) as http:
        resp = await http.post(
            f"{AI_API_BASE}/chat/completions", json=payload, headers=headers
        )
        resp.raise_for_status()
        data = resp.json()
    content = data["choices"][0]["message"]["content"]
    return _parse_verdict(content), content


def _insert_mark_line(html_caption):
    caption = html_caption.rstrip()
    head, sep, tail = caption.rpartition("\n")
    if sep:
        return f"{head}{sep}{AI_MARK}\n{tail}"
    return f"{AI_MARK}\n{caption}"


def schedule_check(msg_id, text, html_caption):
    if not _enabled or not _client:
        return
    if not (text and text.strip()) or not html_caption:
        return
    asyncio.create_task(_check_task(msg_id, text.strip(), html_caption))
    print(f"AI check scheduled for message {msg_id} in {AI_CHECK_DELAY:g}s")


async def _fetch_with_reactions(msg_id):
    msg = await _client.get_messages(_chat_id, ids=msg_id)
    results = getattr(getattr(msg, "reactions", None), "results", None) or []
    return msg, sum(r.count for r in results)


async def _check_task(msg_id, text, html_caption):
    try:
        await asyncio.sleep(AI_CHECK_DELAY)
        if _is_forwarded(msg_id):
            print(f"AI check skipped for {msg_id}: already forwarded")
            return

        msg, total = await _fetch_with_reactions(msg_id)
        if msg is None:
            print(f"AI check skipped for {msg_id}: message not found")
            return
        if total > 0:
            print(f"AI check skipped for {msg_id}: has {total} reaction(s)")
            return

        verdict, raw = await ask_ai(text)
        print(f"AI verdict for {msg_id}: {'ДА' if verdict else 'НЕТ'} ({raw!r})")
        if not verdict or _is_forwarded(msg_id):
            return

        msg, total = await _fetch_with_reactions(msg_id)
        if msg is None:
            print(f"AI forward skipped for {msg_id}: message not found")
            return
        if total > 0:
            print(f"AI forward skipped for {msg_id}: reacted during check ({total})")
            return

        try:
            await _client.edit_message(
                _chat_id, msg_id, _insert_mark_line(html_caption), parse_mode="html"
            )
            print(f"AI mark added to message {msg_id}")
        except Exception as e:
            print(f"AI mark failed for {msg_id}: {e!r}")

        if _forward:
            await _forward(msg)
    except Exception as e:
        print(f"AI check error for message {msg_id}: {e!r}")
