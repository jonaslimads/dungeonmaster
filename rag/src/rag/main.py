from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rag.config import settings
from rag.routers.extraction_router import (
    register_extraction_service,
    router as extraction_router,
)
from rag.routers.health_router import router as health_router
from rag.routers.sources_router import (
    register_source_service,
    router as sources_router,
)
from rag.services.extraction_service import ExtractionService
from rag.services.source_service import SourceService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.sources_dir.mkdir(parents=True, exist_ok=True)

    source_svc = SourceService()
    register_source_service(lambda: source_svc)

    extraction_svc = ExtractionService()
    register_extraction_service(lambda: extraction_svc)

    yield
    await extraction_svc._ingestion.close()


app = FastAPI(
    title="dungeonmaster rag",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(sources_router)
app.include_router(extraction_router)
