from pydantic import BaseModel


class ExtractionJob(BaseModel):
    id: str
    source_id: str
    status: str = "pending"
    progress: dict[str, bool] | None = None
    error: str | None = None
