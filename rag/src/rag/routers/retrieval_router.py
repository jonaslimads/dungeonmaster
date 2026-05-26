from typing import Callable

from fastapi import APIRouter, Depends

from rag.routers.retrieval_requests import SearchRequest
from rag.routers.retrieval_responses import SearchResponse, SearchResult
from rag.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/retrieval", tags=["retrieval"])

_retrieval_factory: Callable[[], RetrievalService] | None = None


def register_retrieval_service(factory: Callable[[], RetrievalService]) -> None:
    global _retrieval_factory
    _retrieval_factory = factory


def get_retrieval_service() -> RetrievalService:
    if _retrieval_factory is None:
        raise RuntimeError("RetrievalService not registered.")
    return _retrieval_factory()


@router.post("/search")
async def search(
    request: SearchRequest,
    svc: RetrievalService = Depends(get_retrieval_service),
) -> SearchResponse:
    results = svc.search(
        query=request.query,
        source_ids=request.source_ids,
        chunk_types=request.chunk_types,
        top_k=request.top_k,
    )
    return SearchResponse(
        query=request.query,
        results=[SearchResult(**r) for r in results],
    )
