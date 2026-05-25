from pydantic import BaseModel


class TextTurnRequest(BaseModel):
    message: str
