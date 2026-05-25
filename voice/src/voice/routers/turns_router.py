from collections.abc import Callable

from fastapi import APIRouter, Depends, File, Header, UploadFile

from voice.auth.token import verify_token
from voice.config import settings
from voice.routers.turns_requests import TextTurnRequest
from voice.routers.turns_responses import TurnResponse
from voice.services.llm_service import LLMService

router = APIRouter(prefix="/api/turn", tags=["turns"])

_llm_factory: Callable[[], LLMService] | None = None


def register_llm(factory: Callable[[], LLMService]) -> None:
    global _llm_factory
    _llm_factory = factory


def get_llm_service() -> LLMService:
    if _llm_factory is None:
        raise RuntimeError("LLMService not registered. Call register_llm() on startup.")
    return _llm_factory()


@router.post("/text", response_model=TurnResponse)
async def turn_text(
    request: TextTurnRequest,
    authorization: str | None = Header(default=None),
    llm: LLMService = Depends(get_llm_service),
) -> TurnResponse:
    verify_token(authorization)

    assistant_text = await llm.generate_reply(request.message)

    return TurnResponse(
        transcript=request.message,
        assistant_text=assistant_text,
    )


@router.post("/audio", response_model=TurnResponse)
async def turn_audio(
    audio: UploadFile = File(...),
    authorization: str | None = Header(default=None),
    llm: LLMService = Depends(get_llm_service),
) -> TurnResponse:
    verify_token(authorization)

    content = await audio.read()

    filename = audio.filename or "recording.webm"
    input_path = settings.input_audio_dir / filename
    input_path.write_bytes(content)

    transcript = "Recebi o áudio. Ainda não transcrevi de verdade."

    assistant_text = await llm.generate_reply(transcript)

    return TurnResponse(
        transcript=transcript,
        assistant_text=assistant_text,
    )
