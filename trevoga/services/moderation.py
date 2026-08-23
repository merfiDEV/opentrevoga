import asyncio
import logging
import re

from trevoga.integrations.ai_client import AIClient


logger = logging.getLogger(__name__)
AI_MARK = "✅ Новина перевірена ШІ на корисність. ШІ може помилятися"
MODERATION_PROMPT = (
    "Ты — строгий фильтр новостей. Тебе дан текст поста из Telegram. "
    "Определи, полезна ли эта новость жителям Донецкой области и переселенцам (ВПО). "
    "Полезная новость: атаки БПЛА, ракет, КАБ, обстрелы, воздушная тревога, "
    "эвакуация, укрытия и приюты, вода, электричество, газ, отопление, транспорт, "
    "выплаты, документы, медицина, работа служб и важные официальные объявления. "
    "Бесполезная новость: реклама, флуд, слухи без деталей, развлечения, спорт, "
    "политика без местной практической пользы. Ответь СТРОГО одним словом: ДА или НЕТ."
)
FIX_PROMPT = (
    "Ти — редактор новин українською мовою. Перепиши текст грамотною українською, "
    "прибери лайку, сленг і сміття, збережи сенс, цифри, топоніми, час і технічні "
    "терміни. Нічого не додавай. Відповідай ТІЛЬКИ відредагованим текстом."
)
YES_RE = re.compile(r"\b(ДА|ТАК|YES|TRUE)\b")
NO_RE = re.compile(r"\b(НЕТ|НІ|NO|FALSE)\b")


def parse_verdict(content: str) -> bool:
    cleaned = (content or "").strip().upper()
    return bool(cleaned and not NO_RE.search(cleaned) and YES_RE.search(cleaned))


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

    async def approve(self, text: str) -> bool:
        return parse_verdict(await self.client.complete(MODERATION_PROMPT, text))

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

    async def fix(self, text: str) -> str | None:
        try:
            return (
                await self.fix_client.complete(FIX_PROMPT, text, temperature=0.3)
                or None
            )
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
            if await self.approve(text):
                await self.on_approved(message_id, insert_ai_mark(caption))
        except Exception:
            logger.exception("AI moderation failed for message %s", message_id)

    async def on_approved(self, message_id: int, caption: str) -> None:
        """Configured by the application after Telegram services are created."""

    def status_text(self) -> str:
        state = "увімкнено ✅" if self.enabled else "вимкнено ❌"
        return f"<blockquote>🤖 AI режим: {state}</blockquote>"
