import json
import logging
from pathlib import Path

from rag.config import settings

logger = logging.getLogger(__name__)


class StorageClient:
    """File-system storage operations for RAG sources."""

    @staticmethod
    def get_source_dir(source_id: str) -> Path:
        return settings.sources_dir / source_id

    @staticmethod
    def get_original_dir(source_id: str) -> Path:
        return StorageClient.get_source_dir(source_id) / "original"

    @staticmethod
    def get_pages_dir(source_id: str) -> Path:
        return StorageClient.get_source_dir(source_id) / "pages"

    @staticmethod
    def get_assets_images_dir(source_id: str) -> Path:
        return StorageClient.get_source_dir(source_id) / "assets" / "images"

    @staticmethod
    def get_assets_thumbnails_dir(source_id: str) -> Path:
        return StorageClient.get_source_dir(source_id) / "assets" / "thumbnails"

    @staticmethod
    def get_extracted_dir(source_id: str) -> Path:
        return StorageClient.get_source_dir(source_id) / "extracted"

    @staticmethod
    def get_canonical_dir(source_id: str) -> Path:
        return StorageClient.get_source_dir(source_id) / "canonical"

    @staticmethod
    def get_reports_dir(source_id: str) -> Path:
        return StorageClient.get_source_dir(source_id) / "reports"

    @staticmethod
    def create_source_dirs(source_id: str) -> None:
        """Create the full directory tree for a source."""
        dirs = [
            StorageClient.get_original_dir(source_id),
            StorageClient.get_pages_dir(source_id),
            StorageClient.get_assets_images_dir(source_id),
            StorageClient.get_assets_thumbnails_dir(source_id),
            StorageClient.get_extracted_dir(source_id),
            StorageClient.get_canonical_dir(source_id),
            StorageClient.get_reports_dir(source_id),
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        logger.info("create_source_dirs: source=%s", source_id)

    @staticmethod
    def save_jsonl(path: Path, records: list[dict]) -> Path:
        """Append records to a JSONL file (one JSON object per line)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info("save_jsonl: path=%s records=%d", path, len(records))
        return path

    @staticmethod
    def save_text(path: Path, content: str) -> Path:
        """Write text content to a file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("save_text: path=%s bytes=%d", path, len(content.encode("utf-8")))
        return path

    @staticmethod
    def load_jsonl(path: Path) -> list[dict]:
        """Read all records from a JSONL file."""
        if not path.exists():
            return []
        records: list[dict] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records
