from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM
    llm_url: str = "http://192.168.0.141:19000/v1"
    llm_password: str = "admin-server"
    llm_model: str = "qwen3.6-27b-mtp-140k"

    # STT — Speech-to-Text via whisper.cpp
    stt_url: str = "http://192.168.0.141:19000/v1"
    stt_password: str = "admin-server"
    stt_model: str = "whisper-base"

    # TTS — Text-to-Speech via Kokoro-FastAPI
    tts_url: str = "http://192.168.0.141:19000/v1"
    tts_password: str = "admin-server"
    tts_model: str = "kokoro"
    tts_voice: str = "pf_dora"
    tts_lang_code: str = "p"

    # Auth
    api_token: str | None = None

    # Data directories
    data_dir: Path = Path("./data")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @property
    def input_audio_dir(self) -> Path:
        return self.data_dir / "audio" / "input"

    @property
    def output_audio_dir(self) -> Path:
        return self.data_dir / "audio" / "output"


settings = Settings()
