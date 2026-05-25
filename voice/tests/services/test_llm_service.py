from unittest.mock import AsyncMock, MagicMock

import pytest

from voice.clients.llm_client import ChatCompletionDTO, LLMClient
from voice.services.llm_service import LLMService


class TestLLMService:
    @pytest.fixture
    def client(self):
        return MagicMock(spec=LLMClient)

    @pytest.fixture
    def service(self, client):
        return LLMService(client=client)

    @pytest.mark.asyncio
    async def test_generate_reply_returns_content(self, service, client):
        client.chat = AsyncMock(return_value=ChatCompletionDTO(content="ola"))
        result = await service.generate_reply("oi")
        assert result == "ola"

    @pytest.mark.asyncio
    async def test_generate_reply_sends_system_prompt(self, service, client):
        client.chat = AsyncMock(return_value=ChatCompletionDTO(content="reply"))
        await service.generate_reply("user message")
        messages = client.chat.call_args[0][0]
        assert messages[0]["role"] == "system"
        assert messages[1] == {"role": "user", "content": "user message"}

    @pytest.mark.asyncio
    async def test_generate_reply_empty_content(self, service, client):
        client.chat = AsyncMock(return_value=ChatCompletionDTO(content=""))
        result = await service.generate_reply("test")
        assert result == ""
