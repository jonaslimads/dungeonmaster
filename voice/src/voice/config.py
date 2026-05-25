from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # OpenAI-compatible LLM (qwen3.6-27b-mtp)
    open_ai_url: str = "http://192.168.0.141:19000/v1"
    open_ai_password: str = "admin-server"
    open_ai_model: str = "qwen3.6-27b-mtp"

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
