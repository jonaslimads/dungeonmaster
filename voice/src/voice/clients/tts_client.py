import asyncio
import logging

import httpx
from pydantic import BaseModel

from voice.config import settings

logger = logging.getLogger(__name__)


class SynthesisDTO(BaseModel):
    audio_bytes: bytes


class TTSClient:
    def __init__(self, *, timeout_seconds: int = 120) -> None:
        self._base_url = settings.tts_url.rstrip("/")
        self._password = settings.tts_password
        self._model = settings.tts_model
        self._lang_code = settings.tts_lang_code
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))
        logger.info(
            "TTSClient: url=%s model=%s lang_code=%s timeout=%ds",
            self._base_url,
            self._model,
            self._lang_code,
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

    async def warm_up(self, *, max_attempts: int = 5, base_delay: float = 2.0) -> None:
        """Send a minimal request to load the model into memory.

        Retries with exponential backoff on transient errors (429, timeouts).
        """
        logger.info("TTSClient warm_up: model=%s", self._model)
        for attempt in range(1, max_attempts + 1):
            try:
                await self.synthesize("ok", "pf_dora")
                logger.info("TTSClient warm_up OK: model=%s", self._model)
                return
            except RuntimeError as exc:
                remaining = max_attempts - attempt
                if remaining == 0:
                    raise
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "TTSClient warm_up attempt %d/%d failed (%s), retrying in %.1fs",
                    attempt,
                    max_attempts,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

    async def synthesize(self, text: str, voice: str) -> SynthesisDTO:
        url = f"{self._base_url}/audio/speech"

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._password:
            headers["Authorization"] = f"Bearer {self._password}"

        payload = {
            "model": self._model,
            "input": text,
            "voice": voice,
            "lang_code": self._lang_code,
            "response_format": "mp3",
        }

        logger.info(
            "synthesize: POST %s payload=%s",
            url,
            payload,
        )

        try:
            response = await self._http.post(
                url,
                json=payload,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            logger.error(
                "synthesize TIMEOUT: url=%s voice=%s error=%s",
                url,
                voice,
                exc,
            )
            raise RuntimeError(f"TTS request timed out: {exc}") from exc
        except httpx.ConnectError as exc:
            logger.error(
                "synthesize CONNECT_FAILED: url=%s voice=%s error=%s",
                url,
                voice,
                exc,
            )
            raise RuntimeError(f"TTS connection failed: {exc}") from exc
        except httpx.RequestError as exc:
            logger.error(
                "synthesize REQUEST_ERROR: url=%s voice=%s error=%s",
                url,
                voice,
                exc,
            )
            raise RuntimeError(f"TTS request failed: {exc}") from exc

        logger.info(
            "synthesize: url=%s voice=%s status=%d body_len=%d",
            url,
            voice,
            response.status_code,
            len(response.content),
        )

        if response.status_code >= 400:
            body_preview = response.text[:1000]
            logger.error(
                "synthesize ERROR_RESPONSE: url=%s voice=%s status=%d body=%s",
                url,
                voice,
                response.status_code,
                body_preview,
            )
            raise RuntimeError(f"TTS returned {response.status_code}: {body_preview}")

        return SynthesisDTO(audio_bytes=response.content)
