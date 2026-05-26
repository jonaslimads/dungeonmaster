import logging
from pathlib import Path

from rag.clients.pdf_client import PdfClient
from rag.clients.storage_client import StorageClient

logger = logging.getLogger(__name__)


class PageRenderingService:
    def __init__(self) -> None:
        self._pdf = PdfClient()
        self._storage = StorageClient()

    def extract_pages(
        self,
        *,
        source_id: str,
        pdf_path: Path,
        page_range: range,
    ) -> list[Path]:
        """Extract individual pages from the PDF as single-page PDFs."""
        pages_dir = self._storage.get_pages_dir(source_id)
        pages_dir.mkdir(parents=True, exist_ok=True)
        extracted: list[Path] = []

        for page_num in page_range:
            page_index = page_num - 1
            output = pages_dir / f"page_{page_num:04d}.pdf"
            page_bytes = self._pdf.extract_page_as_pdf(pdf_path, page_index)
            output.write_bytes(page_bytes)
            extracted.append(output)

        logger.info(
            "extract_pages: source=%s pages=%d-%d",
            source_id,
            page_range[0],
            page_range[-1],
        )
        return extracted
