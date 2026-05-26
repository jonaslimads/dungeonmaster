import asyncio
import io
import logging
import wave
from pathlib import Path

import httpx
from pydantic import BaseModel

from voice.config import settings

logger = logging.getLogger(__name__)


class TranscriptionDTO(BaseModel):
    text: str


class STTClient:
    def __init__(self, *, timeout_seconds: int = 60) -> None:
        self._base_url = settings.stt_url.rstrip("/")
        self._password = settings.stt_password
        self._model = settings.stt_model
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))
        logger.info(
            "STTClient: url=%s model=%s timeout=%ds",
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

    async def warm_up(self, *, max_attempts: int = 5, base_delay: float = 2.0) -> None:
        """Send a minimal audio request to load the model into memory.

        Retries with exponential backoff on transient errors (429, timeouts).
        """
        logger.info("STTClient warm_up: model=%s", self._model)
        for attempt in range(1, max_attempts + 1):
            try:
                await self._transcribe_bytes(_make_silence_wav())
                logger.info("STTClient warm_up OK: model=%s", self._model)
                return
            except RuntimeError as exc:
                remaining = max_attempts - attempt
                if remaining == 0:
                    raise
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "STTClient warm_up attempt %d/%d failed (%s), retrying in %.1fs",
                    attempt,
                    max_attempts,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

    async def transcribe(self, audio_path: Path) -> TranscriptionDTO:
        url = f"{self._base_url}/audio/transcriptions"

        headers: dict[str, str] = {}
        if self._password:
            headers["Authorization"] = f"Bearer {self._password}"

        logger.info("transcribe: POST %s model=%s file=%s", url, self._model, audio_path.name)

        with audio_path.open("rb") as f:
            files = {
                "file": (audio_path.name, f, "audio/wav"),
            }
            data = {
                "model": self._model,
                "language": "pt",
                "response_format": "json",
            }

            try:
                response = await self._http.post(
                    url,
                    files=files,
                    data=data,
                    headers=headers,
                )
            except httpx.TimeoutException as exc:
                logger.error(
                    "transcribe TIMEOUT: url=%s model=%s error=%s",
                    url,
                    self._model,
                    exc,
                )
                raise RuntimeError(f"STT request timed out: {exc}") from exc
            except httpx.ConnectError as exc:
                logger.error(
                    "transcribe CONNECT_FAILED: url=%s model=%s error=%s",
                    url,
                    self._model,
                    exc,
                )
                raise RuntimeError(f"STT connection failed: {exc}") from exc
            except httpx.RequestError as exc:
                logger.error(
                    "transcribe REQUEST_ERROR: url=%s model=%s error=%s",
                    url,
                    self._model,
                    exc,
                )
                raise RuntimeError(f"STT request failed: {exc}") from exc

        logger.info(
            "transcribe: url=%s model=%s status=%d",
            url,
            self._model,
            response.status_code,
        )

        if response.status_code >= 400:
            body_preview = response.text[:1000]
            logger.error(
                "transcribe ERROR_RESPONSE: url=%s model=%s status=%d body=%s",
                url,
                self._model,
                response.status_code,
                body_preview,
            )
            raise RuntimeError(f"STT returned {response.status_code}: {body_preview}")

        try:
            json_data = response.json()
            text = json_data.get("text", "")
            logger.info(
                "transcribe RESPONSE: model=%s text_len=%d text=%r",
                self._model,
                len(text),
                text[:500],
            )
            return TranscriptionDTO(text=text)
        except Exception as exc:
            logger.error(
                "transcribe JSON_PARSE_ERROR: url=%s model=%s error=%s",
                url,
                self._model,
                exc,
            )
            raise RuntimeError("Invalid JSON from STT") from exc

    async def _transcribe_bytes(self, wav_bytes: bytes) -> TranscriptionDTO:
        url = f"{self._base_url}/audio/transcriptions"

        headers: dict[str, str] = {}
        if self._password:
            headers["Authorization"] = f"Bearer {self._password}"

        files = {
            "file": ("warmup.wav", wav_bytes, "audio/wav"),
        }
        data = {
            "model": self._model,
            "language": "pt",
            "response_format": "json",
        }

        response = await self._http.post(
            url,
            files=files,
            data=data,
            headers=headers,
        )

        if response.status_code >= 400:
            raise RuntimeError(f"STT returned {response.status_code}: {response.text[:1000]}")

        json_data = response.json()
        return TranscriptionDTO(text=json_data.get("text", ""))


def _make_silence_wav(duration_seconds: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Generate a silent WAV file in memory."""
    buf = io.BytesIO()
    num_frames = int(sample_rate * duration_seconds)
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * num_frames)
    return buf.getvalue()
