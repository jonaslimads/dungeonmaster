from pydantic import BaseModel


class ChunkSourceRequest(BaseModel):
    force: bool = False
