from pydantic import BaseModel


class RegisterLocalSourceRequest(BaseModel):
    file_name: str
    title: str
    source_type: str
    system: str
    source_id: str | None = None
