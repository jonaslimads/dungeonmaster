import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rag.config import settings
from rag.routers.chunking_router import (
    register_chunking_service,
    router as chunking_router,
)
from rag.routers.extraction_router import (
    register_extraction_service,
    router as extraction_router,
)
from rag.routers.health_router import router as health_router
from rag.routers.retrieval_router import (
    register_retrieval_service,
    router as retrieval_router,
)
from rag.routers.sources_router import (
    register_source_service,
    router as sources_router,
)
from rag.services.chunking_service import ChunkingService
from rag.services.extraction_service import ExtractionService
from rag.services.retrieval_service import RetrievalService
from rag.services.source_service import SourceService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.sources_dir.mkdir(parents=True, exist_ok=True)

    source_svc = SourceService()
    register_source_service(lambda: source_svc)

    extraction_svc = ExtractionService()
    register_extraction_service(lambda: extraction_svc)

    chunking_svc = ChunkingService()
    register_chunking_service(lambda: chunking_svc)

    retrieval_svc = RetrievalService()
    register_retrieval_service(lambda: retrieval_svc)

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
app.include_router(chunking_router)
app.include_router(retrieval_router)
