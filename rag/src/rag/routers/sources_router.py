from typing import Callable

from fastapi import APIRouter, Depends

from rag.routers.sources_requests import RegisterLocalSourceRequest
from rag.routers.sources_responses import SourceResponse, SourcesListResponse
from rag.services.source_service import SourceService

router = APIRouter(prefix="/sources", tags=["sources"])

_source_factory: Callable[[], SourceService] | None = None


def register_source_service(factory: Callable[[], SourceService]) -> None:
    global _source_factory
    _source_factory = factory


def get_source_service() -> SourceService:
    if _source_factory is None:
        raise RuntimeError("SourceService not registered.")
    return _source_factory()


@router.post("/register-local")
async def register_local(
    request: RegisterLocalSourceRequest,
    svc: SourceService = Depends(get_source_service),
) -> SourceResponse:
    source = svc.register_local(
        file_name=request.file_name,
        title=request.title,
        source_type=request.source_type,
        system=request.system,
        source_id=request.source_id,
    )
    return SourceResponse.model_validate(source.model_dump())


@router.get("")
async def list_sources(
    svc: SourceService = Depends(get_source_service),
) -> SourcesListResponse:
    sources = svc.list_sources()
    return SourcesListResponse(
        sources=[SourceResponse.model_validate(s.model_dump()) for s in sources]
    )


@router.get("/{source_id}")
async def get_source(
    source_id: str,
    svc: SourceService = Depends(get_source_service),
) -> SourceResponse | None:
    source = svc.get_source(source_id)
    if source is None:
        return None
    return SourceResponse.model_validate(source.model_dump())
