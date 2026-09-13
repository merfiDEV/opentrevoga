import asyncio
import logging
import uuid

import httpx


logger = logging.getLogger(__name__)
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
# Upstream AI server handles requests sequentially; serialise calls to avoid
# queueing timeouts when moderation, .fix and .aicheck run at the same time.
MAX_CONCURRENT_REQUESTS = 2
# Connection errors mean the server is down: retrying wastes the timeout window.
NON_RETRYABLE_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout)


class AIClient:
    def __init__(self, base_url: str, model: str, api_key: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self._http: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = await httpx.AsyncClient(
                timeout=self.timeout
            ).__aenter__()
        return self._http

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        attempts: int = 3,
    ) -> httpx.Response:
        http = await self._client()
        delay = 0.5
        last_error: Exception | None = None
        async with self._semaphore:
            for attempt in range(1, attempts + 1):
                try:
                    response = await http.request(
                        method,
                        f"{self.base_url}{path}",
                        json=json,
                        headers=self._headers(),
                    )
                    if response.status_code in RETRYABLE_STATUS and attempt < attempts:
                        raise httpx.HTTPStatusError(
                            f"retryable status {response.status_code}",
                            request=response.request,
                            response=response,
                        )
                    response.raise_for_status()
                    return response
                except NON_RETRYABLE_ERRORS as error:
                    logger.error(
                        "AI server unreachable at %s%s (%s: %r), model=%s",
                        self.base_url,
                        path,
                        type(error).__name__,
                        error,
                        self.model,
                    )
                    raise
                except (httpx.TransportError, httpx.TimeoutException) as error:
                    last_error = error
                except httpx.HTTPStatusError as error:
                    if error.response.status_code not in RETRYABLE_STATUS:
                        raise
                    last_error = error
                if attempt < attempts:
                    logger.warning(
                        "AI request %s%s failed (attempt %s/%s, model=%s): %s: %r",
                        self.base_url,
                        path,
                        attempt,
                        attempts,
                        self.model,
                        type(last_error).__name__,
                        last_error,
                    )
                    await asyncio.sleep(delay)
                    delay *= 2
        if last_error is not None:
            logger.error(
                "AI request %s%s exhausted %s attempts (model=%s): %s: %r",
                self.base_url,
                path,
                attempts,
                self.model,
                type(last_error).__name__,
                last_error,
            )
            raise last_error
        raise RuntimeError("AI request failed")

    async def complete(
        self, system_prompt: str, text: str, temperature: float = 0
    ) -> str:
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
        response = await self._request("POST", "/chat/completions", json=payload)
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

    async def list_models(self) -> list[str]:
        response = await self._request("GET", "/models")
        data = response.json()
        raw_models = data.get("data", []) if isinstance(data, dict) else data
        if not isinstance(raw_models, list):
            return []
        models = []
        for item in raw_models:
            if isinstance(item, str) and item.strip():
                models.append(item.strip())
            elif isinstance(item, dict):
                model_id = item.get("id") or item.get("name")
                if isinstance(model_id, str) and model_id.strip():
                    models.append(model_id.strip())
        return sorted(set(models))
