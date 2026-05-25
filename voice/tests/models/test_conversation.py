from voice.models.conversation import Conversation


class TestConversation:
    def test_starts_empty(self):
        conv = Conversation()
        assert conv.turns == []

    def test_append_returns_turn(self):
        conv = Conversation()
        turn = conv.append("hello", "hi")
        assert turn.transcript == "hello"
        assert turn.assistant_text == "hi"

    def test_append_accumulates(self):
        conv = Conversation()
        conv.append("first", "reply1")
        conv.append("second", "reply2")
        assert len(conv.turns) == 2
        assert conv.turns[0].transcript == "first"
        assert conv.turns[1].transcript == "second"
