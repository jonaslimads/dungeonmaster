from pydantic import BaseModel


class SourceResponse(BaseModel):
    id: str
    title: str
    source_type: str
    system: str
    original_path: str
    status: str
    page_count: int | None = None


class SourcesListResponse(BaseModel):
    sources: list[SourceResponse]
