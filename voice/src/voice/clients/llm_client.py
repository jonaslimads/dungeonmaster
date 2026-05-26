import asyncio
import logging
from typing import Any

import httpx

from voice.config import settings

logger = logging.getLogger(__name__)


class ChatCompletionDTO:
    __slots__ = ("content", "usage")

    def __init__(self, content: str, usage: dict | None = None) -> None:
        self.content = content
        self.usage = usage


class LLMClient:
    def __init__(self, *, timeout_seconds: int = 120) -> None:
        self._base_url = settings.llm_url.rstrip("/")
        self._password = settings.llm_password
        self._model = settings.llm_model
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))
        logger.info(
            "LLMClient: url=%s model=%s timeout=%ds",
            self._base_url,
            self._model,
            timeout_seconds,
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def model_name(self) -> str:
        return self._model

    async def close(self) -> None:
        await self._http.aclose()

    async def chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/chat/completions"
        model = payload.get("model", self._model)

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._password:
            headers["Authorization"] = f"Bearer {self._password}"

        logger.debug("chat_completion: POST %s model=%s", url, model)

        try:
            response = await self._http.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            logger.error("chat_completion TIMEOUT: url=%s model=%s error=%s", url, model, exc)
            raise RuntimeError(f"LLM request timed out: {exc.__class__.__name__}: {exc}") from exc
        except httpx.ConnectError as exc:
            logger.error("chat_completion CONNECT_FAILED: url=%s model=%s error=%s", url, model, exc)
            raise RuntimeError(f"LLM connection failed: {exc.__class__.__name__}: {exc}") from exc
        except httpx.RequestError as exc:
            logger.error(
                "chat_completion REQUEST_ERROR: url=%s model=%s error=%s",
                url, model, exc,
            )
            raise RuntimeError(f"LLM request failed: {exc.__class__.__name__}: {exc}") from exc

        logger.info(
            "chat_completion: url=%s model=%s status=%d body_len=%d",
            url, model, response.status_code, len(response.content),
        )

        if response.status_code >= 400:
            body_preview = response.text[:1000]
            logger.error(
                "chat_completion ERROR_RESPONSE: url=%s model=%s status=%d body=%s",
                url, model, response.status_code, body_preview,
            )
            raise RuntimeError(f"LLM returned {response.status_code}: {body_preview}")

        try:
            return response.json()
        except Exception as exc:
            logger.error("chat_completion JSON_PARSE_ERROR: url=%s model=%s error=%s", url, model, exc)
            raise RuntimeError("Invalid JSON from LLM") from exc

    async def warm_up(self, *, max_attempts: int = 5, base_delay: float = 2.0) -> None:
        """Send a minimal request to load the model into memory.

        Retries with exponential backoff on transient errors (429, timeouts).
        """
        logger.info("LLMClient warm_up: model=%s", self._model)
        for attempt in range(1, max_attempts + 1):
            try:
                await self.chat([{"role": "user", "content": "ok"}])
                logger.info("LLMClient warm_up OK: model=%s", self._model)
                return
            except RuntimeError as exc:
                remaining = max_attempts - attempt
                if remaining == 0:
                    raise
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "LLMClient warm_up attempt %d/%d failed (%s), retrying in %.1fs",
                    attempt,
                    max_attempts,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

    async def chat(self, messages: list[dict[str, str]]) -> ChatCompletionDTO:
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
            "chat_template_kwargs": {"enable_thinking": False},
        }

        data = await self.chat_completion(payload)

        try:
            content = data["choices"][0]["message"]["content"]
            logger.info(
                "chat RESPONSE: model=%s content_len=%d usage=%s content=%r",
                self._model,
                len(content),
                data.get("usage"),
                content[:500],
            )
        except (KeyError, IndexError) as exc:
            logger.error("chat_completion EXTRACT_ERROR: %s", exc)
            raise RuntimeError("Invalid response structure from LLM") from exc

        return ChatCompletionDTO(content=content or "", usage=data.get("usage"))
