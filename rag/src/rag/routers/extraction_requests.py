from pydantic import BaseModel, Field


class CreateExtractionJobRequest(BaseModel):
    source_id: str
    use_vlm: bool = False
    force: bool = False
    offset: int = Field(default=0, ge=0, description="Page offset (0-based)")
    limit: int = Field(default=0, ge=0, description="Max pages to process (0 = all)")
    batch_size: int = Field(default=10, ge=1, description="Pages per batch")
