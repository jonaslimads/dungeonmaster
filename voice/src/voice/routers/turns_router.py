import base64
import json
import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, Query, UploadFile
from fastapi.responses import StreamingResponse

from voice.auth.token import verify_token
from voice.config import settings
from voice.routers.turns_requests import TextTurnRequest
from voice.services.llm_service import LLMService
from voice.services.stt_service import STTService
from voice.services.tts_service import TTSService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/turn", tags=["turns"])

_llm_factory: Callable[[], LLMService] | None = None
_stt_factory: Callable[[], STTService] | None = None
_tts_factory: Callable[[], TTSService] | None = None


def register_llm(factory: Callable[[], LLMService]) -> None:
    global _llm_factory
    _llm_factory = factory


def register_stt(factory: Callable[[], STTService]) -> None:
    global _stt_factory
    _stt_factory = factory


def register_tts(factory: Callable[[], TTSService]) -> None:
    global _tts_factory
    _tts_factory = factory


def get_llm_service() -> LLMService:
    if _llm_factory is None:
        raise RuntimeError("LLMService not registered.")
    return _llm_factory()


def get_stt_service() -> STTService:
    if _stt_factory is None:
        raise RuntimeError("STTService not registered.")
    return _stt_factory()


def get_tts_service() -> TTSService:
    if _tts_factory is None:
        raise RuntimeError("TTSService not registered.")
    return _tts_factory()


def _sse_event(event: str, payload: dict | None = None) -> str:
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
    voice: str = Query(default=settings.tts_voice),
    authorization: str | None = Header(default=None),
    llm: LLMService = Depends(get_llm_service),
    stt: STTService = Depends(get_stt_service),
    tts: TTSService = Depends(get_tts_service),
) -> StreamingResponse:
    verify_token(authorization)

    content = await audio.read()
    original_filename = audio.filename or "recording.webm"

    logger.info("[turn/audio] received file=%s size=%d bytes voice=%s", original_filename, len(content), voice)

    raw_path = settings.input_audio_dir / original_filename
    raw_path.write_bytes(content)

    stem = Path(original_filename).stem
    wav_path = settings.input_audio_dir / f"{stem}.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw_path), "-ar", "16000", "-ac", "1", str(wav_path)],
        capture_output=True,
        check=True,
    )
    logger.info("[turn/audio] converted to %s", wav_path)

    async def event_stream():
        yield _sse_event("received", {"filename": original_filename, "size": len(content)})
        logger.info("[turn/audio] sent received event")

        # STT
        transcript = ""
        try:
            logger.info("[turn/audio] transcribing...")
            transcript = await stt.transcribe(wav_path)
            logger.info("[turn/audio] transcript len=%d", len(transcript))
            yield _sse_event("transcript", {"text": transcript})
            logger.info("[turn/audio] sent transcript")
        except Exception as exc:
            logger.error("[turn/audio] STT error: %s", exc)
            yield _sse_event("error", {"message": f"Transcription failed: {exc}"})
            yield _sse_event("done")
            return

        # LLM
        assistant_text = ""
        try:
            logger.info("[turn/audio] calling LLM...")
            assistant_text = await llm.generate_reply(transcript)
            logger.info("[turn/audio] LLM response len=%d", len(assistant_text))
            yield _sse_event("assistant", {"text": assistant_text})
        except Exception as exc:
            logger.error("[turn/audio] LLM error: %s", exc)
            yield _sse_event("error", {"message": str(exc)})
            yield _sse_event("done")
            return

        # TTS
        try:
            logger.info("[turn/audio] synthesizing voice=%s", voice)
            audio_bytes = await tts.synthesize(assistant_text, voice)
            audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
            logger.info("[turn/audio] TTS audio_bytes=%d", len(audio_bytes))
            yield _sse_event("audio", {"voice": voice, "audio": audio_b64})
        except Exception as exc:
            logger.error("[turn/audio] TTS error: %s", exc)
            yield _sse_event("error", {"message": f"Speech synthesis failed: {exc}"})

        yield _sse_event("done")
        logger.info("[turn/audio] done")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
