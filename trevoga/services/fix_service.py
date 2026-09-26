import json
import logging
import time
from collections import OrderedDict

from trevoga.services.moderation import FIX_MODES, sanitize_instruction


logger = logging.getLogger(__name__)

CAPTION_LIMIT = 1024
TEXT_LIMIT = 4096
UNDO_TTL = 600.0
UNDO_MAX = 100

def parse_fixme_answer(answer: str) -> tuple[str, str]:
    """Разобрать ответ ИИ: либо чистый текст, либо JSON {status, text|reason}."""
    raw = (answer or "").strip()
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            status = str(data.get("status") or "").lower()
            if status == "refused":
                return "refused", str(data.get("reason") or "refused")
            if status in {"ok", "fixed"}:
                return "ok", str(data.get("text") or "")
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return "ok", raw


RESULT_OK = "ok"
RESULT_UNCHANGED = "unchanged"
RESULT_ERROR = "error"
RESULT_TOO_LONG = "too_long"


class FixOutcome:
    def __init__(self, status, text="", mode="default", instruction="", error=""):
        self.status = status
        self.text = text
        self.mode = mode
        self.instruction = instruction
        self.error = error


class FixService:
    """Редактирование постов через AI-редактор с превью и откатом."""

    def __init__(
        self,
        moderation,
        *,
        caption_limit=CAPTION_LIMIT,
        text_limit=TEXT_LIMIT,
        autocheck_enabled=False,
        fixme_enabled=False,
    ):
        self.moderation = moderation
        self.caption_limit = caption_limit
        self.text_limit = text_limit
        self.autocheck_enabled = autocheck_enabled
        # .fixme: каждое сообщение админа прогоняется через ИИ (пунктуация).
        self.fixme_enabled = fixme_enabled
        self._undo = OrderedDict()

    def parse_args(self, raw: str) -> tuple[str, str, bool]:
        """Возвращает (mode, instruction, preview)."""
        tokens = raw.split()
        if not tokens:
            return "default", "", False
        preview = False
        mode = "default"
        while tokens and tokens[0].lower() == "test":
            preview = True
            tokens.pop(0)
        if tokens and tokens[0].lower() in FIX_MODES:
            mode = tokens.pop(0).lower()
        while tokens and tokens[-1].lower() == "test":
            preview = True
            tokens.pop()
        instruction = sanitize_instruction(" ".join(tokens))
        return mode, instruction, preview

    async def run(self, original: str, mode: str, instruction: str) -> FixOutcome:
        if not original.strip():
            return FixOutcome(RESULT_ERROR, mode=mode, instruction=instruction)
        try:
            fixed = await self.moderation.fix(original, mode, instruction)
        except Exception as error:  # pragma: no cover - defensive
            logger.exception("Fix service failed")
            return FixOutcome(RESULT_ERROR, mode=mode, instruction=instruction, error=str(error))
        if not fixed or not fixed.strip():
            return FixOutcome(RESULT_ERROR, mode=mode, instruction=instruction)
        fixed = fixed.strip()
        if fixed == original.strip():
            return FixOutcome(RESULT_UNCHANGED, text=original, mode=mode, instruction=instruction)
        return FixOutcome(RESULT_OK, text=fixed, mode=mode, instruction=instruction)

    async def fixme_text(self, text: str) -> str | None:
        """Прогнать текст через ИИ: пунктуация/орфография/перевод на украинский.

        ИИ может вернуть отказ в виде {"status":"refused",...} — тогда
        сообщение не меняем (None).
        """
        if not text.strip():
            return None
        try:
            answer = await self.moderation.fixme(text)
        except Exception:
            logger.exception("fixme failed")
            return None
        if not answer or not answer.strip():
            return None
        answer = answer.strip()
        status, payload = parse_fixme_answer(answer)
        if status != "ok":
            logger.info("fixme refused/skipped: %s", payload)
            return None
        if payload.strip() == text.strip():
            return None
        return payload.strip()

    async def autocheck(self, text: str) -> str | None:
        """Прогон уже обработанного текста через ИИ в режиме official."""
        if not text.strip():
            return None
        try:
            fixed = await self.moderation.fix(text, "official")
        except Exception:
            logger.exception("AI autocheck failed")
            return None
        if not fixed or not fixed.strip():
            return None
        return fixed.strip()

    def limits_for(self, reply) -> int:
        return self.caption_limit if getattr(reply, "media", None) else self.text_limit

    def remember(self, message_id: int, text: str) -> None:
        self._undo[message_id] = (time.monotonic(), text)
        self._undo.move_to_end(message_id)
        while len(self._undo) > UNDO_MAX:
            self._undo.popitem(last=False)

    def pop_undo(self, message_id: int) -> str | None:
        entry = self._undo.pop(message_id, None)
        if not entry:
            return None
        saved_at, text = entry
        if time.monotonic() - saved_at > UNDO_TTL:
            return None
        return text
