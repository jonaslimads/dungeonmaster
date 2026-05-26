from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # VLM — Gemma 4 PDF for layout analysis and OCR
    vlm_url: str = "http://192.168.0.141:19000/v1"
    vlm_password: str = "admin-server"
    vlm_model: str = "gemma-4-31b-pdf"

    # Data directories
    data_dir: Path = Path("./data")
    pdfs_dir: Path | None = None
    rag_sources_dir: Path | None = None

    # PDF rendering
    page_render_dpi: int = 125

    # VLM batch size (pages per request for layout/OCR)
    vlm_batch_pages: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @property
    def input_pdfs_dir(self) -> Path:
        return self.data_dir / "pdfs"

    @property
    def sources_dir(self) -> Path:
        return self.data_dir / "rag" / "sources"


settings = Settings()
