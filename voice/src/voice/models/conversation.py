from pydantic import BaseModel

from voice.models.turn import Turn


class Conversation(BaseModel):
    turns: list[Turn] = []

    def append(self, transcript: str, assistant_text: str) -> Turn:
        turn = Turn(transcript=transcript, assistant_text=assistant_text)
        self.turns.append(turn)
        return turn
