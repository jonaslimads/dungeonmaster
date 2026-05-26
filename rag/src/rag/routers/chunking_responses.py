from pydantic import BaseModel


class ChunkSourceResponse(BaseModel):
    source_id: str
    sections_count: int
    parent_chunks_count: int
    child_chunks_count: int
    status: str
