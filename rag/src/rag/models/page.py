from pydantic import BaseModel

from rag.models.block import PageBlock


class ExtractedPage(BaseModel):
    source_id: str
    page_number: int
    image_path: str
    markdown: str
    blocks: list[PageBlock]
    image_asset_ids: list[str] | None = None
