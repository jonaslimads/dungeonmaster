from pydantic import BaseModel


class Section(BaseModel):
    id: str
    source_id: str
    heading: str
    start_page: int
    end_page: int | None = None
    level: int = 1
