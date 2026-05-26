from pydantic import BaseModel


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class ImageAsset(BaseModel):
    id: str
    source_id: str
    page_number: int
    asset_type: str
    bbox: BoundingBox
    image_path: str
    thumbnail_path: str | None = None
    title: str | None = None
    description: str
    useful_for_gameplay: bool
    linked_block_ids: list[str]
    confidence: float
