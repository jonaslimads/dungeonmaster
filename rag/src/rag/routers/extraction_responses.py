from pydantic import BaseModel


class ExtractionJobResponse(BaseModel):
    id: str
    source_id: str
    status: str
    progress: dict[str, bool] | None = None
    error: str | None = None
    result: dict[str, str] | None = None
