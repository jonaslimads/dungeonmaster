from pydantic import BaseModel


class Section(BaseModel):
    id: str
    source_id: str
    heading: str
    level: int
    page_number: int | None = None
    text: str
    token_count: int
    section_path: list[str]
