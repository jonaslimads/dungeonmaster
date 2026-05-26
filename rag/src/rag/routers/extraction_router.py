from typing import Callable

from fastapi import APIRouter, Depends

from rag.routers.extraction_requests import CreateExtractionJobRequest
from rag.routers.extraction_responses import ExtractionJobResponse
from rag.services.extraction_service import ExtractionService

router = APIRouter(prefix="/extraction", tags=["extraction"])

_extraction_factory: Callable[[], ExtractionService] | None = None


def register_extraction_service(factory: Callable[[], ExtractionService]) -> None:
    global _extraction_factory
    _extraction_factory = factory


def get_extraction_service() -> ExtractionService:
    if _extraction_factory is None:
        raise RuntimeError("ExtractionService not registered.")
    return _extraction_factory()


@router.post("/jobs")
async def create_job(
    request: CreateExtractionJobRequest,
    svc: ExtractionService = Depends(get_extraction_service),
) -> ExtractionJobResponse:
    job = svc.create_job(
        source_id=request.source_id,
        use_vlm=request.use_vlm,
        force=request.force,
        offset=request.offset,
        limit=request.limit,
        batch_size=request.batch_size,
    )
    return ExtractionJobResponse.model_validate(job.model_dump())


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    svc: ExtractionService = Depends(get_extraction_service),
) -> ExtractionJobResponse | None:
    job = svc.get_job(job_id)
    if job is None:
        return None
    return ExtractionJobResponse.model_validate(job.model_dump())


@router.post("/jobs/{job_id}/run")
async def run_job(
    job_id: str,
    svc: ExtractionService = Depends(get_extraction_service),
) -> ExtractionJobResponse:
    job = await svc.run_job(job_id)
    return ExtractionJobResponse.model_validate(job.model_dump())
