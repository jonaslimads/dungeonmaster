from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from voice.clients.llm_client import LLMClient
from voice.config import settings
from voice.routers.turns_router import register_llm, router as turns_router
from voice.services.audio_service import AudioService
from voice.services.llm_service import LLMService


@asynccontextmanager
async def lifespan(app: FastAPI):
    AudioService.ensure_dirs(settings.input_audio_dir, settings.output_audio_dir)
    client = LLMClient()
    app.state.llm_client = client
    register_llm(lambda: LLMService(client=client))
    yield
    await client.close()


app = FastAPI(
    title="dungeonmaster voice",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(turns_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
