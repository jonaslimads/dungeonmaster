from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from voice.clients.llm_client import ChatCompletionDTO, LLMClient


class TestChatCompletionDTO:
    def test_content_and_usage(self):
        dto = ChatCompletionDTO(content="hello", usage={"total_tokens": 10})
        assert dto.content == "hello"
        assert dto.usage == {"total_tokens": 10}

    def test_defaults(self):
        dto = ChatCompletionDTO(content="hi")
        assert dto.usage is None


def _make_client(mock_http: AsyncMock) -> LLMClient:
    with patch("voice.clients.llm_client.settings") as mock_settings:
        mock_settings.open_ai_url = "http://test/v1"
        mock_settings.open_ai_password = "test"
        mock_settings.open_ai_model = "test-model"
        c = LLMClient()
        c._http = mock_http
        return c


class TestLLMClientChatCompletion:
    @pytest.mark.asyncio
    async def test_returns_raw_json(self):
        payload = {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 5}}
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: payload,
                content=b"{}",
                text="",
            )
        )
        c = _make_client(mock_http)
        result = await c.chat_completion({"model": "test", "messages": []})
        assert result == payload

    @pytest.mark.asyncio
    async def test_sends_bearer_auth(self):
        sent_json: dict | None = None
        sent_headers: dict | None = None

        def capture(url, json=None, headers=None):
            nonlocal sent_json, sent_headers
            sent_json = json
            sent_headers = headers
            return MagicMock(
                status_code=200,
                json=lambda: {"choices": [{"message": {"content": "x"}}]},
                content=b"{}",
                text="",
            )

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=capture)
        c = _make_client(mock_http)
        await c.chat_completion({"model": "test", "messages": []})

        assert sent_headers is not None
        assert "Bearer" in sent_headers.get("Authorization", "")

    @pytest.mark.asyncio
    async def test_connection_error(self):
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        c = _make_client(mock_http)

        with pytest.raises(RuntimeError, match="connection failed"):
            await c.chat_completion({"model": "test", "messages": []})

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        c = _make_client(mock_http)

        with pytest.raises(RuntimeError, match="timed out"):
            await c.chat_completion({"model": "test", "messages": []})

    @pytest.mark.asyncio
    async def test_http_error(self):
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(
            return_value=MagicMock(
                status_code=500,
                text="internal error",
                content=b"",
            )
        )
        c = _make_client(mock_http)

        with pytest.raises(RuntimeError, match="500"):
            await c.chat_completion({"model": "test", "messages": []})

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=MagicMock(side_effect=ValueError("bad")),
                content=b"not json",
                text="not json",
            )
        )
        c = _make_client(mock_http)

        with pytest.raises(RuntimeError, match="Invalid JSON"):
            await c.chat_completion({"model": "test", "messages": []})


class TestLLMClientChat:
    @pytest.mark.asyncio
    async def test_returns_dto(self):
        payload = {
            "choices": [{"message": {"content": "response text"}}],
            "usage": {"total_tokens": 20},
        }
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: payload,
                content=b"{}",
                text="",
            )
        )
        c = _make_client(mock_http)
        dto = await c.chat([{"role": "user", "content": "hi"}])

        assert isinstance(dto, ChatCompletionDTO)
        assert dto.content == "response text"
        assert dto.usage == {"total_tokens": 20}

    @pytest.mark.asyncio
    async def test_sends_correct_config(self):
        sent_payload: dict | None = None

        def capture(url, json=None, headers=None):
            nonlocal sent_payload
            sent_payload = json
            return MagicMock(
                status_code=200,
                json=lambda: {"choices": [{"message": {"content": "x"}}]},
                content=b"{}",
                text="",
            )

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=capture)
        c = _make_client(mock_http)
        await c.chat([{"role": "user", "content": "hi"}])

        assert sent_payload is not None
        assert sent_payload["max_tokens"] == 2048
        assert sent_payload["chat_template_kwargs"] == {"enable_thinking": False}

    @pytest.mark.asyncio
    async def test_missing_content_raises(self):
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {"choices": []},
                content=b"{}",
                text="",
            )
        )
        c = _make_client(mock_http)

        with pytest.raises(RuntimeError, match="Invalid response structure"):
            await c.chat([{"role": "user", "content": "hi"}])
