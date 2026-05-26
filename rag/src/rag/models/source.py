from pydantic import BaseModel


class Source(BaseModel):
    id: str
    title: str
    source_type: str
    system: str
    original_path: str
    status: str = "registered"
    page_count: int | None = None
