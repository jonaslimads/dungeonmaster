import logging
from pathlib import Path

from voice.clients.stt_client import STTClient

logger = logging.getLogger(__name__)


class STTService:
    def __init__(self, client: STTClient) -> None:
        self._client = client

    async def transcribe(self, audio_path: Path) -> str:
        dto = await self._client.transcribe(audio_path)
        text = dto.text.strip()
        logger.info("STTService transcribe: file=%s result_len=%d result=%r", audio_path.name, len(text), text[:500])
        return text
