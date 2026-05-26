import shutil
import uuid
from pathlib import Path

from rag.clients.storage_client import StorageClient
from rag.config import settings
from rag.models.source import Source


class SourceService:
    def __init__(self) -> None:
        self._storage = StorageClient()

    def register_local(
        self,
        *,
        file_name: str,
        title: str,
        source_type: str,
        system: str,
        source_id: str | None = None,
    ) -> Source:
        """Register a PDF from data/pdfs/ as a new source."""
        src_pdf = settings.input_pdfs_dir / file_name
        if not src_pdf.exists():
            raise FileNotFoundError(f"PDF not found: {src_pdf}")

        sid = source_id or self._generate_id(file_name)
        self._storage.create_source_dirs(sid)

        dest_pdf = self._storage.get_original_dir(sid) / "source.pdf"
        shutil.copy2(str(src_pdf), str(dest_pdf))

        source = Source(
            id=sid,
            title=title,
            source_type=source_type,
            system=system,
            original_path=str(dest_pdf),
            status="registered",
        )
        return source

    def list_sources(self) -> list[Source]:
        """List all registered sources from the filesystem."""
        sources: list[Source] = []
        if not settings.sources_dir.exists():
            return sources

        for entry in sorted(settings.sources_dir.iterdir()):
            if not entry.is_dir():
                continue
            original_pdf = entry / "original" / "source.pdf"
            if not original_pdf.exists():
                continue

            source = Source(
                id=entry.name,
                title=entry.name,
                source_type="unknown",
                system="unknown",
                original_path=str(original_pdf),
                status=self._detect_status(entry),
            )
            sources.append(source)
        return sources

    def get_source(self, source_id: str) -> Source | None:
        """Get a single source by ID."""
        source_dir = self._storage.get_source_dir(source_id)
        original_pdf = source_dir / "original" / "source.pdf"
        if not original_pdf.exists():
            return None

        return Source(
            id=source_id,
            title=source_id,
            source_type="unknown",
            system="unknown",
            original_path=str(original_pdf),
            status=self._detect_status(source_dir),
        )

    @staticmethod
    def _detect_status(source_dir: Path) -> str:
        """Detect source status from output files."""
        canonical = source_dir / "canonical"
        reports = source_dir / "reports"
        extracted = source_dir / "extracted"

        if (reports / "quality_report.md").exists():
            return "completed"
        if (canonical / "book.md").exists():
            return "markdown_built"
        if (extracted / "vlm_layout.jsonl").exists():
            return "layout_analyzed"
        if (extracted / "native_text.jsonl").exists():
            return "text_extracted"
        if (source_dir / "pages").exists():
            page_files = list((source_dir / "pages").glob("*.png"))
            if page_files:
                return "pages_rendered"
        if (source_dir / "original" / "source.pdf").exists():
            return "registered"
        return "unknown"

    @staticmethod
    def _generate_id(file_name: str) -> str:
        """Generate a source ID from the file name."""
        base = Path(file_name).stem
        cleaned = base.lower().replace(".", "_").replace("-", "_").replace(" ", "_")
        short_uuid = uuid.uuid4().hex[:8]
        return f"{cleaned}_{short_uuid}"
