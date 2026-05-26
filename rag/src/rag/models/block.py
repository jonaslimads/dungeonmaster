from pydantic import BaseModel


class PageBlock(BaseModel):
    id: str
    page_number: int
    block_type: str
    text: str | None = None
    reading_order: int
    confidence: float | None = None
    image_asset_id: str | None = None
    rpg_type: str | None = None
