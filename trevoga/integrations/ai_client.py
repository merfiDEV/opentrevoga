import uuid
import logging

import httpx


logger = logging.getLogger(__name__)


class AIClient:
    def __init__(self, base_url: str, model: str, api_key: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    async def complete(
        self, system_prompt: str, text: str, temperature: float = 0
    ) -> str:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "stream": False,
            "temperature": temperature,
            "user": uuid.uuid4().hex,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            response = await http.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()
        return (data["choices"][0]["message"]["content"] or "").strip()

    async def check(self) -> tuple[bool, str]:
        """Verify that the configured OpenAI-compatible endpoint is usable."""
        try:
            response = await self.complete(
                "Ответь строго одним словом: OK.",
                "Проверка соединения.",
            )
            if not response:
                return False, "нейросеть вернула пустой ответ"
            return True, response
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            logger.warning("AI availability check failed: %s", error)
            return False, str(error)
        except Exception:
            logger.exception("Unexpected AI availability check failure")
            return False, "непредвиденная ошибка"
