from typing import Callable

from fastapi import APIRouter, Depends

from rag.routers.chunking_requests import ChunkSourceRequest
from rag.routers.chunking_responses import ChunkSourceResponse
from rag.services.chunking_service import ChunkingService

router = APIRouter(prefix="/chunking", tags=["chunking"])

_chunking_factory: Callable[[], ChunkingService] | None = None


def register_chunking_service(factory: Callable[[], ChunkingService]) -> None:
    global _chunking_factory
    _chunking_factory = factory


def get_chunking_service() -> ChunkingService:
    if _chunking_factory is None:
        raise RuntimeError("ChunkingService not registered.")
    return _chunking_factory()


@router.post("/sources/{source_id}")
async def chunk_source(
    source_id: str,
    request: ChunkSourceRequest,
    svc: ChunkingService = Depends(get_chunking_service),
) -> ChunkSourceResponse:
    result = svc.chunk_source(source_id=source_id, force=request.force)
    return ChunkSourceResponse(**result)
