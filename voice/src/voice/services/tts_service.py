import logging

from voice.clients.tts_client import TTSClient

logger = logging.getLogger(__name__)


class TTSService:
    def __init__(self, client: TTSClient, default_voice: str) -> None:
        self._client = client
        self._default_voice = default_voice

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        chosen_voice = voice or self._default_voice
        logger.info("TTSService synthesize: requested_voice=%r default_voice=%r chosen=%r text_len=%d", voice, self._default_voice, chosen_voice, len(text))
        dto = await self._client.synthesize(text, chosen_voice)
        logger.info("TTSService synthesize: voice=%s audio_bytes=%d", chosen_voice, len(dto.audio_bytes))
        return dto.audio_bytes
