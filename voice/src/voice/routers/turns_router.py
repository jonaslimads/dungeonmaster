import logging
from collections.abc import Callable

from fastapi import APIRouter, Depends, File, Header, UploadFile
from fastapi.responses import StreamingResponse

from voice.auth.token import verify_token
from voice.config import settings
from voice.routers.turns_requests import TextTurnRequest
from voice.services.llm_service import LLMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/turn", tags=["turns"])

_llm_factory: Callable[[], LLMService] | None = None


def register_llm(factory: Callable[[], LLMService]) -> None:
    global _llm_factory
    _llm_factory = factory


def get_llm_service() -> LLMService:
    if _llm_factory is None:
        raise RuntimeError("LLMService not registered.")
    return _llm_factory()


def _sse_event(event: str, payload: dict | None = None) -> str:
    import json

    line = json.dumps({"event": event, **(payload or {})})
    return f"data: {line}\n\n"


@router.post("/text")
async def turn_text(
    request: TextTurnRequest,
    authorization: str | None = Header(default=None),
    llm: LLMService = Depends(get_llm_service),
) -> StreamingResponse:
    verify_token(authorization)

    logger.info("[turn/text] received message len=%d", len(request.message))

    async def event_stream():
        yield _sse_event("transcript", {"text": request.message})
        logger.info("[turn/text] sending transcript")

        try:
            logger.info("[turn/text] calling LLM...")
            assistant_text = await llm.generate_reply(request.message)
            logger.info("[turn/text] LLM response len=%d", len(assistant_text))
            yield _sse_event("assistant", {"text": assistant_text})
        except Exception as exc:
            logger.error("[turn/text] LLM error: %s", exc)
            yield _sse_event("error", {"message": str(exc)})

        yield _sse_event("done")
        logger.info("[turn/text] done")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/audio")
async def turn_audio(
    audio: UploadFile = File(...),
    authorization: str | None = Header(default=None),
    llm: LLMService = Depends(get_llm_service),
) -> StreamingResponse:
    verify_token(authorization)

    content = await audio.read()
    filename = audio.filename or "recording.webm"

    logger.info("[turn/audio] received file=%s size=%d bytes", filename, len(content))

    input_path = settings.input_audio_dir / filename
    input_path.write_bytes(content)
    logger.info("[turn/audio] saved to %s", input_path)

    transcript = "Recebi o áudio. Ainda não transcrevi de verdade."

    async def event_stream():
        yield _sse_event("received", {"filename": filename, "size": len(content)})
        logger.info("[turn/audio] sent received event")

        yield _sse_event("transcript", {"text": transcript})
        logger.info("[turn/audio] sent transcript")

        try:
            logger.info("[turn/audio] calling LLM...")
            assistant_text = await llm.generate_reply(transcript)
            logger.info("[turn/audio] LLM response len=%d", len(assistant_text))
            yield _sse_event("assistant", {"text": assistant_text})
        except Exception as exc:
            logger.error("[turn/audio] LLM error: %s", exc)
            yield _sse_event("error", {"message": str(exc)})

        yield _sse_event("done")
        logger.info("[turn/audio] done")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
