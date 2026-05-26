from pydantic import BaseModel


class CreateExtractionJobRequest(BaseModel):
    source_id: str
    use_vlm: bool = False
    force: bool = False
