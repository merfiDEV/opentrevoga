import asyncio
import json
import logging
import re

from trevoga.integrations.ai_client import AIClient
from trevoga.models import ModerationResult


logger = logging.getLogger(__name__)
AI_MARK = "✅ Новина перевірена ШІ на корисність. ШІ може помилятися"
MODERATION_PROMPT = (
    "Ты — строгий фильтр новостей. Тебе дан текст поста из Telegram. "
    "Определи, полезна ли эта новость жителям Донецкой области и переселенцам (ВПО). "
    "Полезная новость: атаки БПЛА, ракет, КАБ, обстрелы, воздушная тревога, "
    "эвакуация, укрытия и приюты, вода, электричество, газ, отопление, транспорт, "
    "выплаты, документы, медицина, работа служб и важные официальные объявления. "
    "Бесполезная новость: реклама, флуд, слухи без деталей, развлечения, спорт, "
    "политика без местной практической пользы. Верни только JSON без markdown: "
    '{"useful":true|false,"reason":"advertising|no_local_value|no_specifics|'
    'unconfirmed_rumor|irrelevant|other","reason_text":"краткая причина",'
    '"confidence":0.0}. Для полезной новости reason должен быть null.'
)
FIX_PROMPT = (
    "Ти — редактор новин українською мовою. Перепиши текст грамотною українською, "
    "прибери лайку, сленг і сміття, збережи сенс, цифри, топоніми, час і технічні "
    "терміни. Нічого не додавай. Відповідай ТІЛЬКИ відредагованим текстом."
)
FIX_PROMPTS = {
    "default": FIX_PROMPT,
    "short": FIX_PROMPT + " Зроби текст максимально коротким, зберігши ключові факти.",
    "urgent": FIX_PROMPT
    + " Подай як коротке оперативне повідомлення: загроза, місце, час.",
    "official": FIX_PROMPT + " Використовуй сухий офіційний стиль без емоцій.",
    "neutral": FIX_PROMPT + " Використовуй нейтральний інформаційний стиль.",
}
YES_RE = re.compile(r"\b(ДА|ТАК|YES|TRUE)\b")
NO_RE = re.compile(r"\b(НЕТ|НІ|NO|FALSE)\b")


def parse_verdict(content: str) -> bool:
    cleaned = (content or "").strip().upper()
    return bool(cleaned and not NO_RE.search(cleaned) and YES_RE.search(cleaned))


def parse_result(message_id: int, content: str) -> ModerationResult:
    raw = (content or "").strip()
    try:
        data = json.loads(raw)
        useful = data["useful"]
        if not isinstance(useful, bool):
            raise ValueError("useful must be boolean")
        reason = data.get("reason")
        allowed = {
            "advertising",
            "no_local_value",
            "no_specifics",
            "unconfirmed_rumor",
            "irrelevant",
            "other",
        }
        if reason not in allowed and reason is not None:
            raise ValueError("unknown moderation reason")
        confidence = data.get("confidence")
        if confidence is not None:
            confidence = max(0.0, min(1.0, float(confidence)))
        return ModerationResult(
            message_id,
            useful,
            reason,
            str(data.get("reason_text") or ""),
            confidence,
            raw,
            "approved" if useful else "rejected",
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return ModerationResult(
            message_id,
            False,
            "invalid_response",
            "Невалидный ответ нейросети",
            None,
            raw,
            "invalid_response",
        )


def insert_ai_mark(caption: str) -> str:
    head, separator, tail = caption.rstrip().rpartition("\n")
    return (
        f"{head}{separator}{AI_MARK}\n{tail}" if separator else f"{AI_MARK}\n{caption}"
    )


class ModerationService:
    def __init__(
        self, client: AIClient, fix_client: AIClient, enabled: bool, delay: float
    ):
        self.client = client
        self.fix_client = fix_client
        self.enabled = enabled
        self.delay = delay
        self.tasks: set[asyncio.Task] = set()

    async def moderate(self, message_id: int, text: str) -> ModerationResult:
        return parse_result(
            message_id, await self.client.complete(MODERATION_PROMPT, text)
        )

    async def approve(self, text: str) -> bool:
        return (await self.moderate(0, text)).useful

    async def check_available(self) -> tuple[bool, str]:
        return await self.client.check()

    async def enable(self) -> tuple[bool, str]:
        available, response = await self.check_available()
        if available:
            self.enabled = True
            logger.info("AI moderation enabled after availability check")
        else:
            self.enabled = False
            logger.warning("AI moderation was not enabled: %s", response)
        return available, response

    async def list_models(self) -> list[str]:
        return await self.client.list_models()

    async def set_model(self, model: str) -> bool:
        models = await self.list_models()
        if model not in models:
            return False
        self.client.model = model
        return True

    async def fix(self, text: str, mode: str = "default") -> str | None:
        try:
            prompt = FIX_PROMPTS.get(mode, FIX_PROMPTS["default"])
            return await self.fix_client.complete(prompt, text, temperature=0.3) or None
        except Exception:
            logger.exception("AI text correction failed")
            return None

    def schedule(self, coroutine) -> None:
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def schedule_check(self, message_id: int, text: str, caption: str) -> None:
        if not self.enabled or not text.strip() or not caption:
            return
        self.schedule(self._check(message_id, text, caption))

    async def _check(self, message_id: int, text: str, caption: str) -> None:
        await asyncio.sleep(self.delay)
        try:
            result = await self.moderate(message_id, text)
            await self.on_moderation_result(result)
            if result.useful:
                await self.on_approved(message_id, insert_ai_mark(caption))
        except Exception:
            logger.exception("AI moderation failed for message %s", message_id)

    async def on_approved(self, message_id: int, caption: str) -> None:
        """Configured by the application after Telegram services are created."""

    async def on_moderation_result(self, result: ModerationResult) -> None:
        """Configured by the application to persist moderation decisions."""

    def status_text(self) -> str:
        state = "увімкнено ✅" if self.enabled else "вимкнено ❌"
        return f"<blockquote>🤖 AI режим: {state}</blockquote>"
