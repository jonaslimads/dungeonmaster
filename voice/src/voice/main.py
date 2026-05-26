from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from voice.clients.llm_client import LLMClient
from voice.clients.stt_client import STTClient
from voice.clients.tts_client import TTSClient
from voice.config import settings
from voice.routers.turns_router import register_llm, register_stt, register_tts, router as turns_router
from voice.services.audio_service import AudioService
from voice.services.llm_service import LLMService
from voice.services.stt_service import STTService
from voice.services.tts_service import TTSService


@asynccontextmanager
async def lifespan(app: FastAPI):
    AudioService.ensure_dirs(settings.input_audio_dir, settings.output_audio_dir)

    llm_client = LLMClient()
    app.state.llm_client = llm_client
    register_llm(lambda: LLMService(client=llm_client))

    stt_client = STTClient()
    app.state.stt_client = stt_client
    register_stt(lambda: STTService(client=stt_client))

    tts_client = TTSClient()
    app.state.tts_client = tts_client
    register_tts(lambda: TTSService(client=tts_client, default_voice=settings.tts_voice))

    yield
    await llm_client.close()
    await stt_client.close()
    await tts_client.close()


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


@app.post("/api/warmup")
async def warmup() -> dict[str, str]:
    llm_client: LLMClient = app.state.llm_client
    stt_client: STTClient = app.state.stt_client
    tts_client: TTSClient = app.state.tts_client

    await llm_client.warm_up()
    await stt_client.warm_up()
    await tts_client.warm_up()

    return {"status": "warmed_up"}
