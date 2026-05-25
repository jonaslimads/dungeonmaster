from pydantic import BaseModel


class TurnResponse(BaseModel):
    transcript: str
    assistant_text: str
