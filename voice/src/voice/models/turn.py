from pydantic import BaseModel


class Turn(BaseModel):
    transcript: str
    assistant_text: str
