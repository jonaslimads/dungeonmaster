from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    source_ids: list[str] | None = None
    chunk_types: list[str] | None = None
    top_k: int = 8
