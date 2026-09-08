import os
import uuid
import logging

import httpx
from dotenv import load_dotenv


logger = logging.getLogger(__name__)

load_dotenv()


def _env_float(name, default):
    try:
        return float(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


AI_FIX_API_BASE = (
    os.getenv("AI_FIX_API_BASE")
    or os.getenv("AI_API_BASE")
    or "http://127.0.0.1:8000/v1"
).rstrip("/")
AI_FIX_MODEL = os.getenv("AI_FIX_MODEL") or os.getenv("AI_MODEL") or "deepseek-v4-flash"
AI_FIX_API_KEY = os.getenv("AI_FIX_API_KEY") or os.getenv("AI_API_KEY") or ""
AI_FIX_TIMEOUT = _env_float("AI_FIX_TIMEOUT", 60.0)

SYSTEM_PROMPT = (
    "Ти — редактор новин українською мовою. Тобі дано текст поста з Telegram, "
    "який може містити мат, сленг, русизми та помилки. "
    "Завдання: переписати текст грамотною українською мовою, прибрати лайку, "
    "сленг і сміття, зберегти оригінальний сенс, цифри, топоніми, час подій "
    "та технічні терміни (БПЛА, Шахед, КАБ, РСЗВ, РСЗО, ФПВ, балістичні ракети). "
    "Нічого не додавати від себе, без коментарів і префіксів. "
    "Відповідай ТІЛЬКИ відредагованим текстом."
)


async def fix_text(text):
    headers = {}
    if AI_FIX_API_KEY:
        headers["Authorization"] = f"Bearer {AI_FIX_API_KEY}"
    payload = {
        "model": AI_FIX_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "stream": False,
        "temperature": 0.3,
        "user": uuid.uuid4().hex,
    }
    try:
        async with httpx.AsyncClient(timeout=AI_FIX_TIMEOUT) as http:
            resp = await http.post(
                f"{AI_FIX_API_BASE}/chat/completions", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return (content or "").strip() or None
    except Exception as e:
        logger.exception("AI fix error")
        return None
