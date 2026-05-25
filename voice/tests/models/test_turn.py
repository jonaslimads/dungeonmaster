from voice.models.turn import Turn


class TestTurn:
    def test_creation(self):
        turn = Turn(transcript="hello", assistant_text="hi back")
        assert turn.transcript == "hello"
        assert turn.assistant_text == "hi back"

    def test_repr(self):
        turn = Turn(transcript="a", assistant_text="b")
        assert "Turn" in repr(turn)
