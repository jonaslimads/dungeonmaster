import logging

from voice.clients.llm_client import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a local voice-first RPG assistant.

- Always respond in Brazilian Portuguese.
- Keep answers concise and natural for speech.
- Be direct and helpful.
- Avoid long lists unless asked.
""".strip()


class LLMService:

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def generate_reply(self, transcript: str) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ]

        logger.info("LLMService generate_reply: input_len=%d input=%r", len(transcript), transcript[:500])

        dto = await self._client.chat(messages)
        logger.info("LLMService generate_reply: output_len=%d output=%r", len(dto.content), dto.content[:500])
        return dto.content
