from pydantic import BaseModel


class SearchResult(BaseModel):
    chunk_id: str
    parent_id: str | None
    title: str
    chunk_type: str
    source_id: str
    page_start: int | None
    page_end: int | None
    score: float
    text: str
    parent_text: str | None
    parent_title: str | None
    token_count: int


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
