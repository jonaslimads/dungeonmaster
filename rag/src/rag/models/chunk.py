from pydantic import BaseModel


class Chunk(BaseModel):
    id: str
    source_id: str
    chunk_type: str
    title: str
    text: str
    parent_id: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    section_path: list[str]
    token_count: int
    image_asset_ids: list[str] | None = None
    metadata: dict[str, str | int | float | bool | list[str]] | None = None
