from unittest.mock import AsyncMock

import pytest

from voice.routers.turns_requests import TextTurnRequest
from voice.routers.turns_responses import TurnResponse


class TestTextTurnRequest:
    def test_valid(self):
        req = TextTurnRequest(message="hello")
        assert req.message == "hello"

    def test_empty_message(self):
        req = TextTurnRequest(message="")
        assert req.message == ""


class TestTurnResponse:
    def test_valid(self):
        resp = TurnResponse(transcript="hi", assistant_text="hello")
        assert resp.transcript == "hi"
        assert resp.assistant_text == "hello"

    def test_serialization(self):
        resp = TurnResponse(transcript="a", assistant_text="b")
        data = resp.model_dump()
        assert data == {"transcript": "a", "assistant_text": "b"}
