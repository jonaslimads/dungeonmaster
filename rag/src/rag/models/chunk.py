from pydantic import BaseModel


class Chunk(BaseModel):
    id: str
    source_id: str
    chunk_type: str
    text: str
    page_range: list[int]
    parent_id: str | None = None
    section_id: str | None = None
    image_asset_ids: list[str] | None = None
